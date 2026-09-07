# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route_sale = fields.Selection(
        string="Use Approval Route for Sales",
        selection=[
            ('no', 'No'),
            ('required', 'Required')
        ],
        default='no',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route_sale = fields.Selection(
        string="Use Approval Route for Sales",
        related='company_id.use_approval_route_sale',
        readonly=False,
    )
