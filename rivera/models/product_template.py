# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Brand',
        index=True,
    )
    rja_code = fields.Char(
        string='RJA Code',
        index=True,
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    brand_id = fields.Many2one(
        related='product_tmpl_id.brand_id',
        string='Brand',
        store=True,
        readonly=False,
    )
    rja_code = fields.Char(
        related='product_tmpl_id.rja_code',
        string='RJA Code',
        store=True,
        readonly=False,
    )
