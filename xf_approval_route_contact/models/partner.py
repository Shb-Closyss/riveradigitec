from odoo.tools.safe_eval import safe_eval
from odoo import fields, api, models
from odoo.exceptions import ValidationError



class ResPartnerInherit(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'approval.route.document']

    active = fields.Boolean(default=False, copy=False,
                            help="By unchecking the active field, you may hide a fiscal position without deleting it.")
    sale_approval_status = fields.Selection(
        [('new', "Draft"), ('sent', 'Sent for Approval'), ('approval', "Approved"), ('reject', "Rejected")],
        default='new', copy=False, tracking=True)
    approval_user_ids = fields.Many2many('res.users', compute='compute_approval_users', store=True, copy=False)
    use_approval_route_customer = fields.Selection(selection=[
        ('no', 'No'),
        ('required', 'Required')
    ],
        string="Use Approval Invoice",
        compute='_compute_approval_route_out_invoice'
    )


    def _compute_approval_route_out_invoice(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'xf_approval_route_contact.use_approval_route_customer'
        )
        for rec in self:
            rec.use_approval_route_customer = param

    use_approval_route_vendor = fields.Selection(selection=[
        ('no', 'No'),
        ('required', 'Required')
    ],
        string="Use Approval Invoice",
        compute='_compute_approval_route_in_invoice'
    )

    def _compute_approval_route_in_invoice(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'xf_approval_route_contact.use_approval_route_vendor'
        )
        for rec in self:
            rec.use_approval_route_vendor = param

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_approval_users(self):
        for sheet in self:
            if sheet.approval_route_stage_ids:
                approval_user_ids = sheet.approval_route_stage_ids.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                sheet.approval_user_ids = approval_user_ids
            else:
                sheet.approval_user_ids = False

    @api.depends('use_approval_route_customer', 'use_approval_route_vendor', 'sale_approval_status', 'active')
    def compute_check_approval_needed_or_not(self):
        for rec in self:
            rec.need_approval = False
            # Only applicable when the record is inactive (pending approval)
            if rec.active or rec.sale_approval_status == 'approval':
                continue
            if rec.use_approval_route_customer == 'no' and rec.use_approval_route_vendor == 'no':
                continue
            routes = self.env['approval.route'].sudo().search([
                ('model', '=', rec._name),
            ])
            matched = False
            for route in routes:
                if route.custom_domain:
                    try:
                        domain = safe_eval(route.custom_domain)
                        if isinstance(domain, (list, tuple)):
                            if self.with_context(active_test=False).search_count(
                                [('id', '=', rec.id)] + domain, limit=1
                            ):
                                matched = True
                                break
                    except Exception:
                        pass
                else:
                    matched = True
                    break
            rec.need_approval = matched

    need_approval = fields.Boolean(compute='compute_check_approval_needed_or_not', store=False)

    def action_send_approval(self):
        for contact in self:
            if contact.active == False and not contact.approval_route_id:
                routes = self.env['approval.route'].search(
                    [('model', '=', contact._name)]
                )
                route_to_assign = None
                for route in routes:
                    if route.custom_domain:
                        try:
                            domain = safe_eval(route.custom_domain)
                            if isinstance(domain, (list, tuple)):
                                if self.with_context(active_test=False).search_count(
                                    [('id', '=', contact.id)] + domain, limit=1
                                ):
                                    route_to_assign = route
                                    break
                        except Exception:
                            pass
                    else:
                        route_to_assign = route
                        break
                if not route_to_assign:
                    raise ValidationError('Approval Route is not set for contact approval')
                contact.approval_route_id = route_to_assign.id
            if contact.active == False and contact.approval_route_id:
                contact.generate_approval_route()
                contact.sale_approval_status = 'sent'
                if contact.next_approval_stage_id:
                    contact._action_send_to_approve()

    def action_approve(self):
        if self.active == False and self.approval_route_id:
            self.active = True
            self.sale_approval_status = 'approval'
            self.message_post(body=f"{self.name} has been approved by {self.env.user.name}")
            recipients = []
            for stage in self.approval_route_stage_ids:
                if stage.create_uid and stage.create_uid.email:
                    recipients.append(stage.create_uid.email)
            recipients = list(set(recipients))  # Remove duplicates
            if recipients:
                email_to = ",".join(recipients)
                subject = f"Document Approved: {self.name}"
                body_html = f"""<p>Hello,</p>
                                <p>The following document has been <b>approved</b>:</p>
                                <ul>
                                    <li><b>Document Type:</b> {self._description}</li>
                                    <li><b>Document Name:</b> {self.name}</li>
                                    <li><b>Approved By:</b> {self.env.user.name}</li>
                                    <li><b>Approval Date:</b> {fields.Datetime.now()}</li>
                                </ul>
                                <p><a href="/web#id={self.id}&model={self._name}&view_type=form">
                                    Open Document
                                </a></p>
                                <p>Regards,<br/>{self.env.user.name}</p>
                            """
                mail = self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email_to,
                    'body_html': body_html,
                })
                mail.send()

    def action_reject(self):
        self._cr.execute(f"DELETE FROM xf_reject_reason where create_uid= {self.env.user.id}")
        return {
            'name': 'Reject',
            'type': 'ir.actions.act_window',
            'res_model': 'xf.reject.reason',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id}
        }

    def action_reject_button(self):
        self._action_reject()
        self.message_post(body=f"Rejected by: {self.env.user.name}. \nRejection Reason: {self._context.get('reject_reason')}.")
        self.sale_approval_status = 'reject'
        self.approval_route_id = False
        self.approval_route_stage_ids = False
        self.approval_user_ids = False
        recipients = []
        for stage in self.approval_route_stage_ids:
            if stage.create_uid and stage.create_uid.email:
                recipients.append(stage.create_uid.email)
        recipients = list(set(recipients))  # Remove duplicates
        if recipients:
            email_to = ",".join(recipients)
            subject = f"Document Reject: {self.name}"
            body_html = f"""<p>Hello,</p>
                                        <p>The following document has been <b>Rejected</b>:</p>
                                        <ul>
                                            <li><b>Document Type:</b> {self._description}</li>
                                            <li><b>Document Name:</b> {self.name}</li>
                                            <li><b>Rejected By:</b> {self.env.user.name}</li>
                                            <li><b>Rejected Date:</b> {fields.Datetime.now()}</li>
                                            <li><b>Rejected Reason:</b>{self._context.get('reject_reason')}</li>
                                        </ul>
                                        <p><a href="/web#id={self.id}&model={self._name}&view_type=form">
                                            Open Document
                                        </a></p>
                                        <p>Regards,<br/>{self.env.user.name}</p>
                                    """
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': email_to,
                'body_html': body_html,
            })
            mail.send()

    def action_unarchive(self):
        if not self.env.user.has_group('base.group_erp_manager'):
            raise ValidationError('You are not allowed to unarchive the record. Contact your Administrator')
        for rec in self:
            rec.message_post(body=f"Records has been unarchive by {self.env.user.name}")
        return super().action_unarchive()

    def action_archive(self):
        # if not self.env.user.has_group('base.group_erp_manager'):
        #     raise ValidationError('You are not allowed to archive the record. Contact your Administrator')
        for rec in self:
            rec.message_post(body=f"Record has been archive by {self.env.user.name}")
        return super().action_archive()

    @api.ondelete(at_uninstall=False)
    def _prevent_delete_non_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError('You are not allowed to delete this record. Contact your Administrator.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.parent_id:
                rec.active = True
                rec.sale_approval_status = 'approval'
        return records

    def write(self, vals):
        if self.env.context.get('skip_approval'):
            return super().write(vals)
        old_parent_map = {rec.id: rec.parent_id.id for rec in self}
        old_company_map = {rec.id: rec.is_company for rec in self}
        res = super().write(vals)
        for rec in self:
            old_parent_id = old_parent_map.get(rec.id)
            old_is_company = old_company_map.get(rec.id)
            parent_added = (
                    'parent_id' in vals
                    and vals.get('parent_id')
                    and not old_parent_id
                    and rec.parent_id)
            if parent_added:
                rec.with_context(skip_approval=True).write({
                    'active': True,
                    'sale_approval_status': 'approval',
                    'approval_route_id': False,
                    'approval_route_stage_ids': False,
                    'approval_user_ids': False,
                })
                continue
            parent_removed = (
                    'parent_id' in vals
                    and not vals.get('parent_id')
                    and old_parent_id
                    and not rec.parent_id)
            company_changed = (
                    'is_company' in vals
                    and not old_is_company
                    and rec.is_company)
            approval_required = parent_removed or company_changed
            if approval_required and not rec.approval_route_id:
                rec.with_context(skip_approval=True).write({
                    'active': False,
                    'sale_approval_status': 'new'})
        return res