# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class InheritAccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'approval.route.document']

    sale_approval_status = fields.Selection([
        ('new', "Draft"),
        ('sent', 'Sent for Approval'),
        ('approval', "Approved"),
        ('reject', "Rejected")
    ], string="Approval Status", default='new', copy=False, tracking=True)

    use_approval_route_out_invoice = fields.Selection(
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        string="Use Approval Route (Invoice)",
        compute='_compute_approval_route_out_invoice',
        store=True,
    )

    use_approval_route_in_invoice = fields.Selection(
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        string="Use Approval Route (Bill)",
        compute='_compute_approval_route_in_invoice',
        store=True,
    )

    use_approval_route_entry = fields.Selection(
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        string="Use Approval Route (Journal Entry)",
        compute='_compute_approval_route_entry',
        store=True,
    )

    approval_route_id = fields.Many2one('approval.route', string="Approval Route", readonly=True, copy=False)
    reject_button_visibility = fields.Boolean(compute='compute_reject_button_visibility', copy=False, compute_sudo=True)
    approval_user_ids = fields.Many2many('res.users', string="Approvers", compute='compute_approval_users', store=True, copy=False, compute_sudo=True)
    approval_route_stage_ids = fields.One2many('approval.route.document.stage', 'res_id', string="Approval Stages")
    can_approve = fields.Boolean(compute="compute_can_approve", store=True, compute_sudo=True)
    need_approval = fields.Boolean(compute='compute_check_approval_needed_or_not', store=False)

    @api.depends('company_id', 'company_id.use_approval_route_out_invoice')
    def _compute_approval_route_out_invoice(self):
        for rec in self:
            if rec.company_id.use_approval_route_out_invoice and rec.move_type in ['out_invoice', 'out_refund']:
                rec.use_approval_route_out_invoice = rec.company_id.use_approval_route_out_invoice
            else:
                rec.use_approval_route_out_invoice = 'no'

    @api.depends('company_id', 'company_id.use_approval_route_in_invoice')
    def _compute_approval_route_in_invoice(self):
        for rec in self:
            if rec.company_id.use_approval_route_in_invoice and rec.move_type in ['in_invoice', 'in_refund']:
                rec.use_approval_route_in_invoice = rec.company_id.use_approval_route_in_invoice
            else:
                rec.use_approval_route_in_invoice = 'no'

    @api.depends('company_id', 'company_id.use_approval_route_entry')
    def _compute_approval_route_entry(self):
        for rec in self:
            if rec.company_id.use_approval_route_entry and rec.move_type == 'entry':
                rec.use_approval_route_entry = rec.company_id.use_approval_route_entry
            else:
                rec.use_approval_route_entry = 'no'

    @api.depends_context('uid')
    @api.depends('approval_route_id', 'current_approval_stage_id')
    def compute_can_approve(self):
        for account in self:
            if (account.use_approval_route_out_invoice != 'no' or 
                account.use_approval_route_in_invoice != 'no' or 
                account.use_approval_route_entry != 'no') and account.approval_route_id:
                account.can_approve = account.is_current_approver
            else:
                account.can_approve = False

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_reject_button_visibility(self):
        for rec in self:
            stages = rec.sudo().approval_route_stage_ids
            if stages:
                approval_user_ids = stages.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                rec.reject_button_visibility = True if self.env.user.id in approval_user_ids else False
            else:
                rec.reject_button_visibility = False

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_approval_users(self):
        for rec in self:
            stages = rec.sudo().approval_route_stage_ids
            if stages:
                approval_user_ids = stages.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                rec.approval_user_ids = approval_user_ids
            else:
                rec.approval_user_ids = False

    @api.depends('move_type', 'company_id', 'sale_approval_status',
                 'use_approval_route_out_invoice', 'use_approval_route_in_invoice',
                 'use_approval_route_entry')
    def compute_check_approval_needed_or_not(self):
        for rec in self:
            rec.need_approval = False

            if rec.state != 'draft' or rec.sale_approval_status == 'approval':
                continue

            # Check if the approval route is enabled for this move type
            if rec.move_type in ['out_invoice', 'out_refund']:
                if rec.use_approval_route_out_invoice == 'no':
                    continue
            elif rec.move_type in ['in_invoice', 'in_refund']:
                if rec.use_approval_route_in_invoice == 'no':
                    continue
            elif rec.move_type == 'entry':
                if rec.use_approval_route_entry == 'no':
                    continue
            else:
                continue

            routes = self.env['approval.route'].sudo().search([
                ('model', '=', rec._name),
                ('company_id', '=', rec.company_id.id),
                ('move_type', '=', rec.move_type)
            ])
            matched_route = False
            for route in routes:
                if route.custom_domain:
                    # Route has a domain: only apply if the record matches
                    try:
                        domain = safe_eval(route.custom_domain)
                        if isinstance(domain, (list, tuple)):
                            matched = self.search_count(
                                [('id', '=', rec.id)] + domain, limit=1
                            )
                            if matched:
                                matched_route = True
                                break
                    except Exception:
                        pass
                else:
                    # Generic route without domain — applies to all records
                    matched_route = True
                    break

            rec.need_approval = matched_route

    def action_send_approval(self):
        for rec in self:
            if rec.state == 'draft' and not rec.approval_route_id:
                # Find matching route
                routes = self.env['approval.route'].sudo().search([
                    ('model', '=', rec._name),
                    ('company_id', '=', rec.company_id.id),
                    ('move_type', '=', rec.move_type)
                ])
                route_to_assign = None
                for route in routes:
                    if route.custom_domain:
                        try:
                            domain = safe_eval(route.custom_domain)
                            if isinstance(domain, (list, tuple)):
                                matched = self.search_count([('id', '=', rec.id)] + domain, limit=1)
                                if matched:
                                    route_to_assign = route
                                    break
                        except Exception:
                            pass
                    else:
                        route_to_assign = route
                        break
                
                if not route_to_assign:
                    raise ValidationError(_('Need to create Approval Configuration for this Document Type'))
                rec.approval_route_id = route_to_assign.id
            
            if rec.state == 'draft' and rec.approval_route_id:
                rec.generate_approval_route()
                rec.sale_approval_status = 'sent'
                if rec.next_approval_stage_id:
                    rec._action_send_to_approve()

    def action_approve(self):
        action = False
        for rec in self:
            if (rec.use_approval_route_out_invoice != 'no' or 
                rec.use_approval_route_in_invoice != 'no' or 
                rec.use_approval_route_entry != 'no') and rec.approval_route_id:
                rec._action_approve()
                if rec._is_fully_approved():
                    rec.sale_approval_status = 'approval'
                    if rec.move_type in ['out_invoice', 'in_invoice']:
                        res = rec.with_context(tds_approved=True, skip_approval=True).action_post()
                    else:
                        res = rec.with_context(skip_approval=True).action_post()
                    if isinstance(res, dict):
                        action = res
                    rec.message_post(body=_("Approved and Posted by: %s") % self.env.user.name)
                    rec._send_approval_email_notification()
        return action

    def action_reject(self):
        self._cr.execute(f"DELETE FROM reject_reason where create_uid = {self.env.user.id}")
        return {
            'name': 'Reject',
            'type': 'ir.actions.act_window',
            'res_model': 'reject.reason',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id}
        }

    def action_reject_button(self):
        for rec in self:
            rec._action_reject()
            rec.message_post(body=f"Rejected by: {self.env.user.name}. \nRejection Reason: {self._context.get('reject_reason')}.")
            rec.sale_approval_status = 'reject'
            rec.approval_route_id = False
            rec.approval_route_stage_ids = False
            rec.approval_user_ids = False
            rec._send_rejection_email_notification()

    def button_draft(self):
        res = super(InheritAccountMove, self).button_draft()
        self.sale_approval_status = 'new'
        self.approval_route_id = False
        self.approval_route_stage_ids = False
        self.approval_user_ids = False
        return res

    def action_post(self):
        for rec in self:
            if not self.env.context.get('skip_approval'):
                if rec.need_approval:
                    # Block posting and trigger approval flow for both 'required'
                    # and 'optional' routes, but only when the record matches
                    # the route's domain (already checked in need_approval).
                    rec.action_send_approval()
                    return False
        return super(InheritAccountMove, self).action_post()

    def _send_approval_email_notification(self):
        self.ensure_one()
        recipients = []
        reply_to_list = set()
        for stage in self.approval_route_stage_ids:
            if stage.create_uid and stage.create_uid.email:
                recipients.append(stage.create_uid.email)
            for user in stage.user_ids:
                if user.email:
                    reply_to_list.add(user.email)
        recipients = list(set(recipients))  # Remove duplicates
        reply_to = ",".join(reply_to_list) if reply_to_list else False
        if recipients:
            email_to = ",".join(recipients)
            subject = f"Document Approved: {self.name or self.id}"
            body_html = f"""
                <p>Hello,</p>
                <p>The following document has been <b>approved</b>:</p>
                <ul>
                    <li><b>Document Type:</b> {self._description}</li>
                    <li><b>Document Name:</b> {self.name or self.id}</li>
                    <li><b>Approved By:</b> {self.env.user.name}</li>
                    <li><b>Approval Date:</b> {fields.Datetime.now()}</li>
                </ul>
                <p><a href="/web#id={self.id}&model={self._name}&view_type=form">
                    Open Document
                </a></p>
                <p>Regards,<br/>{self.env.user.name}</p>
            """
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email_to,
                    'body_html': body_html,
                    'reply_to': reply_to,
                }).send()
            except Exception:
                pass

    def _send_rejection_email_notification(self):
        self.ensure_one()
        recipients = []
        reply_to_list = set()
        for stage in self.approval_route_stage_ids:
            if stage.create_uid and stage.create_uid.email:
                recipients.append(stage.create_uid.email)
            for user in stage.user_ids:
                if user.email:
                    reply_to_list.add(user.email)
        recipients = list(set(recipients))  # Remove duplicates
        reply_to = ",".join(reply_to_list) if reply_to_list else False
        if recipients:
            email_to = ",".join(recipients)
            subject = f"Document Rejected: {self.name or self.id}"
            body_html = f"""
                <p>Hello,</p>
                <p>The following document has been <b>Rejected</b>:</p>
                <ul>
                    <li><b>Document Type:</b> {self._description}</li>
                    <li><b>Document Name:</b> {self.name or self.id}</li>
                    <li><b>Rejected By:</b> {self.env.user.name}</li>
                    <li><b>Reject Date:</b> {fields.Datetime.now()}</li>
                    <li><b>Rejected Reason:</b> {self._context.get('reject_reason')}</li>
                </ul>
                <p><a href="/web#id={self.id}&model={self._name}&view_type=form">
                    Open Document
                </a></p>
                <p>Regards,<br/>{self.env.user.name}</p>
            """
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email_to,
                    'body_html': body_html,
                    'reply_to': reply_to,
                }).send()
            except Exception:
                pass
