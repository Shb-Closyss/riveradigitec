# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Brand',
        compute='_compute_brand_id',
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends('sale_line_ids.brand_id', 'purchase_line_id.brand_id', 'product_id.brand_id')
    def _compute_brand_id(self):
        for line in self:
            sale_brand = line.sale_line_ids.brand_id[:1]
            if sale_brand:
                line.brand_id = sale_brand
            elif line.purchase_line_id and line.purchase_line_id.brand_id:
                line.brand_id = line.purchase_line_id.brand_id
            elif line.product_id and line.product_id.brand_id:
                line.brand_id = line.product_id.brand_id
            else:
                line.brand_id = False
