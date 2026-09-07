# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class SalesOrderInherit(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'approval.route.document']

    sale_approval_status = fields.Selection(
        [('new', "Draft"), ('sent', 'Sent for Approval'), ('approval', "Approved"), ('reject', "Rejected")],
        default='new', copy=False)
    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_sale',
    )
    approval_route_id = fields.Many2one('approval.route', readonly=True, copy=False)
    reject_button_visibility = fields.Boolean(compute='compute_reject_button_visibility', copy=False, compute_sudo=True)
    approval_user_ids = fields.Many2many('res.users', compute='compute_approval_users', store=True, copy=False, compute_sudo=True)
    approval_route_stage_ids = fields.One2many('approval.route.document.stage', 'res_id')
    can_approve = fields.Boolean(compute="compute_can_approve", store=True, compute_sudo=True)
    need_approval = fields.Boolean(compute='compute_check_approval_needed_or_not', store=False)

    @api.depends_context('uid')
    @api.depends('approval_route_id', 'current_approval_stage_id')
    def compute_can_approve(self):
        for order in self:
            if order.use_approval_route != 'no' and order.approval_route_id:
                # approvers = purchase.current_approval_stage_id.user_ids
                order.can_approve = order.is_current_approver

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_reject_button_visibility(self):
        for order in self:
            stages = order.sudo().approval_route_stage_ids
            if stages:
                approval_user_ids = stages.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                order.reject_button_visibility = True if self.env.user.id in approval_user_ids else False
            else:
                order.reject_button_visibility = False

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_approval_users(self):
        for order in self:
            stages = order.sudo().approval_route_stage_ids
            if stages:
                approval_user_ids = stages.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                order.approval_user_ids = approval_user_ids
            else:
                order.approval_user_ids = False

    @api.depends('use_approval_route', 'sale_approval_status', 'state')
    def compute_check_approval_needed_or_not(self):
        for rec in self:
            rec.need_approval = False
            if rec.use_approval_route == 'no' or rec.sale_approval_status == 'approval':
                continue
            routes = self.env['approval.route'].sudo().search([
                ('model', '=', rec._name),
                ('company_id', '=', rec.company_id.id),
            ])
            matched = False
            for route in routes:
                if route.custom_domain:
                    try:
                        domain = safe_eval(route.custom_domain)
                        if isinstance(domain, (list, tuple)):
                            if self.search_count([('id', '=', rec._origin.id)] + domain, limit=1):
                                matched = True
                                break
                    except Exception:
                        pass
                else:
                    matched = True
                    break
            rec.need_approval = matched

    def action_send_approval(self):
        for order in self:
            if order.state == 'draft' and order.use_approval_route != 'no' and not order.approval_route_id:
                routes = self.env['approval.route'].search([
                    ('model', '=', order._name),
                    ('company_id', '=', order.company_id.id),
                ])
                route_to_assign = None
                for route in routes:
                    if route.custom_domain:
                        try:
                            domain = safe_eval(route.custom_domain)
                            if isinstance(domain, (list, tuple)):
                                if self.search_count([('id', '=', order._origin.id)] + domain, limit=1):
                                    route_to_assign = route
                                    break
                        except Exception:
                            pass
                    else:
                        route_to_assign = route
                        break
                if not route_to_assign:
                    raise ValidationError('Need to create Approval Configuration')
                order.approval_route_id = route_to_assign.id
            if order.state == 'draft' and order.use_approval_route != 'no' and order.approval_route_id:
                order.generate_approval_route()
                order.sale_approval_status = 'sent'
                if order.next_approval_stage_id:
                    order._action_send_to_approve()

    def action_confirm(self):
        for rec in self:
            if not self.env.context.get('skip_approval'):
                if rec.need_approval:
                    rec.action_send_approval()
                    return False
        return super().action_confirm()

    def action_approve(self):
        if self.use_approval_route != 'no' and self.approval_route_id:
            self._action_approve()
            if self._is_fully_approved():
                self.sale_approval_status = 'approval'
                self.with_context(create_rfq=True).with_user(self.user_id).sudo().action_confirm()

    # def action_reject(self):
    #     action = self.env["ir.actions.act_window"]._for_xml_id('xf_approval_route_base.xf_reject_reason_actions')
    #     action['context'] = {'default_res_model': self._name, 'default_res_id': self.id}
    #     return action

    def action_reject(self):
        # self._cr.execute(f"DELETE FROM reject_reason where create_uid= {self.env.user.id}")
        return {
            'name': 'Reject',
            'type': 'ir.actions.act_window',
            'res_model': 'reject.reason.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_id': self.id}
        }

    def action_reject_button(self):
        self._action_reject()
        self.message_post(body=f"Rejected by: {self.env.user.name}. \nRejection Reason: {self._context.get('reject_reason')}.")
        self.approval_route_id = False
        self.sale_approval_status = 'reject'
        self.approval_route_stage_ids = False
        self.approval_user_ids = False
