# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    manufacturing_date = fields.Date(
        string='Manufacturing Date',
        compute='_compute_manufacturing_date',
        store=True,
        readonly=False,
        precompute=True,
        copy=False,
        help='Manufacturing Date of the lot/serial number.',
    )

    @api.depends('move_id.manufacturing_date')
    def _compute_manufacturing_date(self):
        for line in self:
            if line.move_id and line.move_id.manufacturing_date and not line.manufacturing_date:
                line.manufacturing_date = line.move_id.manufacturing_date

    def _prepare_new_lot_vals(self):
        vals = super()._prepare_new_lot_vals()
        mfg_date = self.manufacturing_date or (self.move_id and self.move_id.manufacturing_date)
        if mfg_date:
            vals['manufacturing_date'] = mfg_date
        return vals
