from odoo import models,fields,api

class StockLotInherit(models.Model):
    _inherit = "stock.lot"

    under_warrenty = fields.Boolean("Under Warrenty")
    warrenty_expiry_date = fields.Date("Warrenty Expiry Date")