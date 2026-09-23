# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        readonly=True,
    )
    warehouse_notified = fields.Boolean(
        string='Warehouse Notified',
        copy=False,
        default=False,
    )
    order_id = fields.Char(
        string='Order ID',
        copy=False,
    )
    online_invoice_no = fields.Char(
        string='Online Invoice No.',
        copy=False,
    )

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        if self.order_id:
            invoice_vals['order_id'] = self.order_id
        if self.online_invoice_no:
            invoice_vals['online_invoice_no'] = self.online_invoice_no
        return invoice_vals

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if not order.warehouse_notified:
                order._send_warehouse_notification()
                order.warehouse_notified = True
        return res

    def _send_warehouse_notification(self):
        self.ensure_one()
        partners = self.warehouse_id.warehouse_user_ids.partner_id
        if not partners:
            return
        template = self.env.ref('rivera.mail_template_sale_order_warehouse_notification', raise_if_not_found=False)
        if template:
            emails = [p.email_formatted for p in partners if p.email]
            email_values = {'recipient_ids': [(6, 0, partners.ids)]}
            if emails:
                email_values['email_to'] = ', '.join(emails)
            template.send_mail(
                self.id,
                force_send=True,
                email_values=email_values,
            )
