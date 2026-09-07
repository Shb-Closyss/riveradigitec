from odoo import fields, api, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class AccountAccountInherit(models.Model):
    _name = 'account.account'
    _inherit = ['account.account', 'approval.route.document']

    # active = fields.Boolean(default=True, tracking=True)
    approval_state = fields.Selection([('new', 'Draft'), ('sent', "Send for Approval"),
                                       ('approve', "Approve"), ('reject', "Reject")], default='new', copy=False,
                                      tracking=True)
    active = fields.Boolean(default=False, tracking=True)
    need_approval = fields.Boolean(compute='compute_check_approval_needed_or_not', store=False)

    @api.depends('approval_state', 'active')
    def compute_check_approval_needed_or_not(self):
        for rec in self:
            rec.need_approval = False
            if rec.active or rec.approval_state == 'approve':
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


    def action_send_for_approval(self):
        """Button will only visible when in Setting or Company Approval route for purchase is set as Required"""
        for rec in self:
            if not rec.approval_route_id:
                routes = self.env['approval.route'].search([
                    ('model', '=', rec._name)
                ])
                route_to_assign = None
                for route in routes:
                    if route.custom_domain:
                        try:
                            domain = safe_eval(route.custom_domain)
                            if isinstance(domain, (list, tuple)):
                                if self.with_context(active_test=False).search_count(
                                    [('id', '=', rec.id)] + domain, limit=1
                                ):
                                    route_to_assign = route
                                    break
                        except Exception:
                            pass
                    else:
                        route_to_assign = route
                        break
                if not route_to_assign:
                    raise ValidationError('Need to create Approval Configuration')
                rec.approval_route_id = route_to_assign.id
            rec.generate_approval_route()
            rec.approval_state = 'sent'
            if rec.next_approval_stage_id:
                rec._action_send_to_approve()

    def action_approve(self):
        if self.approval_route_id:
            self._action_approve()
        if self._is_fully_approved():
            self.approval_state = 'approve'
            self.active = True
            # self.with_context(create_rfq=True,skip_approval=True).with_user(self.user_id).sudo().button_confirm()
            # self.message_post(body=f"Approved by: {self.env.user.name}")
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
                    subject = f"Document Approved: {self.name}"
                    body_html = f"""
                                                    <p>Hello,</p>
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
                        'reply_to': reply_to,
                    })
                    mail.send()

    def action_reject_button(self):
        # self._action_reject()
        self.message_post(
            body=f"Rejected by: {self.env.user.name}. \nRejection Reason: {self._context.get('reject_reason')}.")
        self.approval_route_id = False
        self.approval_state = 'reject'
        # self.approval_user_ids = False
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
            subject = f"Document Reject: {self.name}"
            body_html = f"""
                                <p>Hello,</p>
                                <p>The following document has been <b>Rejected</b>:</p>
                                <ul>
                                    <li><b>Document Type:</b> {self._description}</li>
                                    <li><b>Document Name:</b> {self.name}</li>
                                    <li><b>Rejected By:</b> {self.env.user.name}</li>
                                    <li><b>Reject Date:</b> {fields.Datetime.now()}</li>
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
                'reply_to': reply_to,
            })
            mail.send()
        self.approval_route_stage_ids = False

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

    def action_archive(self):
        for rec in self:
            if not self.env.user.has_group('base.group_system'):
                raise ValidationError("You are not authorised to archive the Accounts")
            rec.message_post(body="Record has been archive from Action/Archive")
        return super().action_archive()

    def action_unarchive(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError("You are not authorised to unarchive the Accounts")
        for rec in self:
            rec.message_post(body="Record has been Unarchive from Action/Unarchive")
        return super().action_unarchive()
