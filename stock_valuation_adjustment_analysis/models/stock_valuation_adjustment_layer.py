# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools

class StockValuationAdjustmentLayer(models.Model):
    _name = 'stock.valuation.adjustment.layer'
    _description = 'Stock Valuation Adjustment Layer'
    _auto = False
    _rec_name = 'id'
    _order = 'date desc, cost_id, product_id'

    cost_id = fields.Many2one('stock.landed.cost', 'Landed Cost', readonly=True)
    cost_line_id = fields.Many2one('stock.landed.cost.lines', 'Cost Line', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    quantity = fields.Float('Quantity', readonly=True)
    former_cost = fields.Monetary('Original Value', currency_field='currency_id', readonly=True)
    additional_landed_cost = fields.Monetary('Additional Landed Cost', currency_field='currency_id', readonly=True)
    final_cost = fields.Monetary('New Value', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    date = fields.Date('Date', readonly=True)
    picking_id = fields.Many2one('stock.picking', 'Transfer', readonly=True)

    @api.readonly
    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.landed.cost',
            'views': [(False, 'form')],
            'res_id': self.cost_id.id,
            'target': 'current',
            'context': dict(self.env.context),
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s AS (
                SELECT
                    val.id as id,
                    val.cost_id as cost_id,
                    val.cost_line_id as cost_line_id,
                    val.product_id as product_id,
                    val.quantity as quantity,
                    val.former_cost as former_cost,
                    val.additional_landed_cost as additional_landed_cost,
                    val.final_cost as final_cost,
                    comp.currency_id as currency_id,
                    lc.company_id as company_id,
                    lc.date as date,
                    sm.picking_id as picking_id
                FROM stock_valuation_adjustment_lines val
                JOIN stock_landed_cost lc ON (val.cost_id = lc.id)
                JOIN res_company comp ON (lc.company_id = comp.id)
                LEFT JOIN stock_move sm ON (val.move_id = sm.id)
                WHERE lc.state = 'done'
            )
        """ % self._table)
