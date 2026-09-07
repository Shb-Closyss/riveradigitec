from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class PurchaseOrderInherit(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'approval.route.document']

    approval_state = fields.Selection([('new', 'Need to Send for Approval'), ('sent', "Send for Approval"),
                                       ('approve', "Approve"), ('reject', "Reject")], default='new', copy=False,
                                      tracking=True)
    need_approval = fields.Boolean(compute='compute_check_approval_needed_or_not')
    use_approval_route = fields.Selection(string="Use Approval Route", related='company_id.use_approval_route_purchase')

    def button_confirm(self):
        for rec in self:
            if not self.env.context.get('skip_approval'):
                if rec.need_approval:
                    rec.action_send_for_approval()
                    return False
        res = super().button_confirm()
        return res

    @api.depends('use_approval_route', 'approval_state')
    def compute_check_approval_needed_or_not(self):
        for rec in self:
            rec.need_approval = False
            if rec.use_approval_route == 'no' or rec.approval_state == 'approve':
                continue
            purchase_routes = self.env['approval.route'].sudo().search([
                ('model', '=', rec._name),
                ('company_id', '=', rec.company_id.id),
            ])
            matched = False
            for route in purchase_routes:
                if route.custom_domain:
                    try:
                        domain = safe_eval(route.custom_domain)
                        if not isinstance(domain, (list, tuple)):
                            continue
                        if self.search_count([('id', '=', rec._origin.id)] + domain, limit=1):
                            matched = True
                            break
                    except Exception:
                        pass
                else:
                    # Generic route without domain — applies to all records
                    matched = True
                    break
            rec.need_approval = matched

    def action_send_for_approval(self):
        """Button will only visible when in Setting or Company Approval route for purchase is set as Required"""
        for rec in self:
            if rec.state in ('draft', 'sent'):  # Approval will send only when state are draft and sent
                if not rec.approval_route_id:
                    routes = self.env['approval.route'].search([
                        ('model', '=', rec._name),
                        ('company_id', '=', rec.company_id.id),
                    ])
                    route_to_assign = None
                    for route in routes:
                        if route.custom_domain:
                            try:
                                domain = safe_eval(route.custom_domain)
                                if isinstance(domain, (list, tuple)):
                                    if self.search_count([('id', '=', rec._origin.id)] + domain, limit=1):
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
            self.with_context(create_rfq=True,skip_approval=True).with_user(self.user_id).sudo().button_confirm()
            self.message_post(body=f"Approved by: {self.env.user.name}")
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
                                    <li><b>Rejecred By:</b> {self.env.user.name}</li>
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

    def button_draft(self):
        self.write({'state': 'draft', 'approval_state': 'new'})
        return {}