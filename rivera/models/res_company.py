# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    overwrite_invoice_number = fields.Boolean(
        string='Overwrite Invoice Number',
        default=False,
        help='If checked, the Odoo-generated invoice number will be replaced by the Online Invoice No. when posting customer invoices.',
    )
