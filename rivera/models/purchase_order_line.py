# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

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

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move=move)
        if self.brand_id:
            res['brand_id'] = self.brand_id.id
        return res

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        res = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        if self.brand_id:
            res['brand_id'] = self.brand_id.id
        return res
