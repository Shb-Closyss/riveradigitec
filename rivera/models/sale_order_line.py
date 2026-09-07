# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Brand',
        compute='_compute_brand_id',
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends('product_id')
    def _compute_brand_id(self):
        for line in self:
            line.brand_id = line.product_id.brand_id or False

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.brand_id:
            res['brand_id'] = self.brand_id.id
        return res

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        if self.brand_id:
            values['brand_id'] = self.brand_id.id
        return values
