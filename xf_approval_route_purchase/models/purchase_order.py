# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from odoo.exceptions import ValidationError


class PurchaseOrderInherit(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_purchase',
    )
    # no_approval = fields.Boolean(default=False,compute='depends_on_type',store=True)
    approval_route_id = fields.Many2one('approval.route', readonly=True,copy=False)
    reject_button_visibility = fields.Boolean(compute='compute_reject_button_visibility', copy=False, compute_sudo=True)
    approval_user_ids = fields.Many2many('res.users', compute='compute_approval_users', store=True, copy=False, compute_sudo=True)
    approval_route_stage_ids = fields.One2many('approval.route.document.stage', 'res_id')
    can_approve = fields.Boolean(compute="compute_can_approve", store=True, compute_sudo=True)

    # @api.depends('purchase_type')
    # def depends_on_type(self):
    #     for rec in self:
    #         if rec.purchase_type and rec.purchase_type == 'internal':
    #             rec.no_approval = True
    #         else:
    #             rec.no_approval = False

    @api.depends_context('uid')
    @api.depends('approval_route_id', 'current_approval_stage_id')
    def compute_can_approve(self):
        for purchase in self:
            if purchase.use_approval_route != 'no' and purchase.approval_route_id:
                # approvers = purchase.current_approval_stage_id.user_ids
                purchase.can_approve = purchase.is_current_approver

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_reject_button_visibility(self):
        for sheet in self:
            stages = sheet.sudo().approval_route_stage_ids
            if stages:
                approval_user_ids = stages.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                sheet.reject_button_visibility = True if self.env.user.id in approval_user_ids else False
            else:
                sheet.reject_button_visibility = False

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_approval_users(self):
        for sheet in self:
            stages = sheet.sudo().approval_route_stage_ids
            if stages:
                approval_user_ids = stages.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                sheet.approval_user_ids = approval_user_ids
            else:
                sheet.approval_user_ids = False

    def action_send_approval(self):
        for purchase in self:
            if purchase.state == 'draft' and purchase.use_approval_route != 'no' and not purchase.approval_route_id:
                route_id = self.env['approval.route'].search([('model', '=', purchase._name)])
                for route in route_id:
                    if route.custom_domain:
                        list_condition = eval(route.custom_domain)
                        list_condition.append(('id', '=', self._origin.id))
                        check_lead = self.env[self._name].search(list_condition)
                        if check_lead:
                            purchase.approval_route_id = route.id
                            break
                    else:
                        continue
            if not purchase.approval_route_id:
                raise ValidationError(
                    f'There is no Approval Process created for Purchase')
            if purchase.state == 'draft' and purchase.use_approval_route != 'no' and purchase.approval_route_id:
                # Generate approval workflow and send expense sheet to approve
                purchase.generate_approval_route()
                if purchase.next_approval_stage_id:
                    purchase._action_send_to_approve()

    def action_approve(self):
        if self.use_approval_route != 'no' and self.approval_route_id:
            self._action_approve()
            if self._is_fully_approved():
                self.button_confirm()

    def action_reject(self):
        action = self.env["ir.actions.act_window"]._for_xml_id('xf_approval_route_base.xf_reject_reason_actions')
        action['context'] = {'default_res_model': self._name, 'default_res_id': self.id}
        return action
