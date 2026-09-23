# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    order_id = fields.Char(
        string='Order ID',
        copy=False,
    )
    online_invoice_no = fields.Char(
        string='Online Invoice No.',
        copy=False,
    )

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        for move in posted:
            if (
                move.is_sale_document(include_receipts=True)
                and move.company_id.overwrite_invoice_number
                and move.online_invoice_no
                and move.online_invoice_no.strip()
            ):
                move.name = move.online_invoice_no.strip()
        return posted
