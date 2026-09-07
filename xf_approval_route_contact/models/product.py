from odoo import fields, api, models
from pytz import timezone
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class ProductTemplateInherit(models.Model):
    _name = 'product.template'
    _inherit = ['product.template',  'approval.route.document']

    active = fields.Boolean('Active', default=True, copy=False,
                            help="If unchecked, it will allow you to hide the product without removing it.")
    sale_approval_status = fields.Selection(
        [('new', "Draft"), ('sent', 'Sent for Approval'), ('approval', "Approved"), ('reject', "Rejected")],
        default='new', copy=False)
    approval_user_ids = fields.Many2many('res.users', compute='compute_approval_users', store=True, copy=False)
    need_approval = fields.Boolean(compute='compute_check_approval_needed_or_not', store=False)
    
    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.user_ids')
    def compute_approval_users(self):
        for sheet in self:
            if sheet.approval_route_stage_ids:
                approval_user_ids = sheet.approval_route_stage_ids.filtered(lambda x: x.user_ids).mapped('user_ids').ids
                sheet.approval_user_ids = approval_user_ids
            else:
                sheet.approval_user_ids = False


    @api.depends('sale_approval_status', 'active')
    def compute_check_approval_needed_or_not(self):
        for rec in self:
            rec.need_approval = False
            if rec.active or rec.sale_approval_status == 'approval':
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

    def action_send_approval(self):
        for template in self:
            if template.active == False and not template.approval_route_id:
                routes = self.env['approval.route'].search(
                    [('model', '=', template._name)]
                )
                route_to_assign = None
                for route in routes:
                    if route.custom_domain:
                        try:
                            domain = safe_eval(route.custom_domain)
                            if isinstance(domain, (list, tuple)):
                                if self.with_context(active_test=False).search_count(
                                    [('id', '=', template.id)] + domain, limit=1
                                ):
                                    route_to_assign = route
                                    break
                        except Exception:
                            pass
                    else:
                        route_to_assign = route
                        break
                if route_to_assign:
                    template.approval_route_id = route_to_assign.id
            if template.active == False and template.approval_route_id:
                template.generate_approval_route()
                template.sale_approval_status = 'sent'
                if template.next_approval_stage_id:
                    template._action_send_to_approve()

    def action_approve(self):
        if self.active == False and self.approval_route_id:
            # self._action_approve()
            # if self._is_fully_approved():
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
        self._cr.execute(f"DELETE FROM reject_reason_wiz where create_uid= {self.env.user.id}")
        return {
            'name': 'Reject',
            'type': 'ir.actions.act_window',
            'res_model': 'reject.reason.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_tmpl_id': self.id}
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
            subject = f"Document Rejected: {self.name}"
            body_html = f"""<p>Hello,</p>
                                        <p>The following document has been <b>rejected</b>:</p>
                                        <ul>
                                            <li><b>Document Type:</b> {self._description}</li>
                                            <li><b>Document Name:</b> {self.name}</li>
                                            <li><b>Rejected By:</b> {self.env.user.name}</li>
                                            <li><b>Rejected Date:</b> {fields.Datetime.now()}</li>
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
            archived_time_utc = fields.Datetime.now()
            user_tz = self.env.user.tz or 'Asia/Kolkata'
            tz = timezone(user_tz)
            archived_time_local = archived_time_utc.astimezone(tz)
            formatted_time = archived_time_local.strftime('%d-%b-%Y %I:%M %p')
            rec.write({'archived_date': archived_time_utc})
            rec.message_post(body=f"Record unarchived by {self.env.user.name} on {formatted_time}")
        return super().action_unarchive()

    def action_archive(self):
        if not self.env.user.has_group('base.group_erp_manager'):
            raise ValidationError('You are not allowed to archive the record. Contact your Administrator')
        for rec in self:
            archived_time_utc = fields.Datetime.now()
            user_tz = self.env.user.tz or 'Asia/Kolkata'
            tz = timezone(user_tz)
            archived_time_local = archived_time_utc.astimezone(tz)
            formatted_time = archived_time_local.strftime('%d-%b-%Y %I:%M %p')
            rec.write({'archived_date': archived_time_utc})
            rec.message_post(body=f"Record archived by {self.env.user.name} on {formatted_time}")
        return super().action_archive()


class ProductProductInherit(models.Model):
    _inherit = 'product.product'

    def action_unarchive(self):
        if not self.env.user.has_group('base.group_erp_manager'):
            raise ValidationError('You are not allowed to unarchive the record. Contact your Administrator')
        for rec in self:
            archived_time_utc = fields.Datetime.now()
            user_tz = self.env.user.tz or 'Asia/Kolkata'
            tz = timezone(user_tz)
            archived_time_local = archived_time_utc.astimezone(tz)
            formatted_time = archived_time_local.strftime('%d-%b-%Y %I:%M %p')
            rec.write({'archived_date': archived_time_utc})
            rec.message_post(body=f"Record unarchived by {self.env.user.name} on {formatted_time}")
        return super().action_unarchive()

    def action_archive(self):
        if not self.env.user.has_group('base.group_erp_manager'):
            raise ValidationError('You are not allowed to archive the record. Contact your Administrator')
        for rec in self:
            archived_time_utc = fields.Datetime.now()
            user_tz = self.env.user.tz or 'Asia/Kolkata'
            tz = timezone(user_tz)
            archived_time_local = archived_time_utc.astimezone(tz)
            formatted_time = archived_time_local.strftime('%d-%b-%Y %I:%M %p')
            rec.write({'archived_date': archived_time_utc})
            rec.message_post(body=f"Record archived by {self.env.user.name} on {formatted_time}")
        return super().action_archive()


