# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route_chart_of_account = fields.Selection(
        string="Use Approval Route for Chart of Account",
        selection=[('no', 'None'), ('required', 'Required')],default='no',)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route_chart_of_account = fields.Selection(string="Use Approval Route for Chart Of Account",
                                                           related='company_id.use_approval_route_purchase',
                                                           readonly=False,)
