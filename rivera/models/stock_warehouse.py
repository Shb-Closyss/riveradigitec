# -*- coding: utf-8 -*-
from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    warehouse_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='stock_warehouse_res_users_rel',
        column1='warehouse_id',
        column2='user_id',
        string='Warehouse Users/Team',
        help='Users who will receive an email notification when a sales order is confirmed for this warehouse.',
    )
