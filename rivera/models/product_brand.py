# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'Product Brand'
    _order = 'name'

    name = fields.Char(string='Brand Name', required=True, translate=True)
    description = fields.Text(string='Description')
    image_1920 = fields.Image(string='Brand Logo', max_width=1920, max_height=1920)
    active = fields.Boolean(string='Active', default=True)
    partner_id = fields.Many2one('res.partner', string='Partner / Manufacturer')
    product_ids = fields.One2many('product.template', 'brand_id', string='Products')
    product_count = fields.Integer(string='Product Count', compute='_compute_product_count')

    @api.depends('product_ids')
    def _compute_product_count(self):
        for brand in self:
            brand.product_count = len(brand.product_ids)

    def action_view_products(self):
        self.ensure_one()
        return {
            'name': 'Products',
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('brand_id', '=', self.id)],
            'context': {'default_brand_id': self.id},
        }
