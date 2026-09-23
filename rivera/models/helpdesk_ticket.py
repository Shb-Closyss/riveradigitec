# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        domain="[('sale_ok', '=', True)]",
        tracking=True,
        groups='stock.group_stock_user',
    )
    lot_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Lot/Serial Number',
        domain="product_id and [('product_id', '=', product_id)] or []",
        tracking=True,
        groups='stock.group_stock_user',
    )
    manufacturing_date = fields.Date(
        string='Manufacturing Date',
        related='lot_id.manufacturing_date',
        readonly=True,
        store=True,
        groups='stock.group_stock_user',
    )
    import_date = fields.Date(
        string='Import Date (GRN)',
        related='lot_id.import_date',
        readonly=True,
        store=True,
        groups='stock.group_stock_user',
    )
    under_warrenty = fields.Boolean(
        string='Under Warrenty',
        related='lot_id.under_warrenty',
        readonly=True,
        store=True,
        groups='stock.group_stock_user',
    )
    warrenty_expiry_date = fields.Date(
        string='Warrenty Expiry Date',
        related='lot_id.warrenty_expiry_date',
        readonly=True,
        store=True,
        groups='stock.group_stock_user',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.lot_id and self.product_id and self.lot_id.product_id != self.product_id:
            self.lot_id = False
            self.manufacturing_date = False
            self.import_date = False
            self.under_warrenty = False
            self.warrenty_expiry_date = False

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            self.manufacturing_date = self.lot_id.manufacturing_date
            self.import_date = self.lot_id.import_date
            self.under_warrenty = self.lot_id.under_warrenty
            self.warrenty_expiry_date = self.lot_id.warrenty_expiry_date
            if not self.product_id and self.lot_id.product_id:
                self.product_id = self.lot_id.product_id
        else:
            self.manufacturing_date = False
            self.import_date = False
            self.under_warrenty = False
            self.warrenty_expiry_date = False
