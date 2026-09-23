# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Brand',
        compute='_compute_brand_id',
        store=True,
        readonly=False,
        precompute=True,
    )
    manufacturing_date = fields.Date(
        string='Manufacturing Date',
        copy=False,
        help='Manufacturing Date of the lot/serial number to be received.',
    )

    @api.depends('sale_line_id.brand_id', 'purchase_line_id.brand_id', 'product_id.brand_id')
    def _compute_brand_id(self):
        for move in self:
            if move.sale_line_id and move.sale_line_id.brand_id:
                move.brand_id = move.sale_line_id.brand_id
            elif move.purchase_line_id and move.purchase_line_id.brand_id:
                move.brand_id = move.purchase_line_id.brand_id
            elif move.product_id and move.product_id.brand_id:
                move.brand_id = move.product_id.brand_id
            else:
                move.brand_id = False

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        for move in res:
            if move.picking_code == 'incoming' and not move.picking_id:
                receipt_date = fields.Date.context_today(move)
                for line in move.move_line_ids:
                    if line.lot_id:
                        vals = {'import_date': receipt_date}
                        mfg_date = line.manufacturing_date or move.manufacturing_date
                        if mfg_date:
                            vals['manufacturing_date'] = mfg_date
                        line.lot_id.write(vals)
        return res


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values):
        res = super()._get_stock_move_values(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)
        if values.get('brand_id'):
            res['brand_id'] = values['brand_id']
        elif values.get('sale_line_id'):
            sale_line = self.env['sale.order.line'].browse(values['sale_line_id'])
            if sale_line.brand_id:
                res['brand_id'] = sale_line.brand_id.id
        return res
