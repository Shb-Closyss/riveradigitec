# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route_out_invoice = fields.Selection(
        string="Use Approval Route for Invoices",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )

    use_approval_route_in_invoice = fields.Selection(
        string="Use Approval Route for Bills",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )

    use_approval_route_entry = fields.Selection(
        string="Use Approval Route for Journal Entries",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route_out_invoice = fields.Selection(
        string="Use Approval Route for Invoices",
        related='company_id.use_approval_route_out_invoice',
        readonly=False,
    )

    use_approval_route_in_invoice = fields.Selection(
        string="Use Approval Route for Bills",
        related='company_id.use_approval_route_in_invoice',
        readonly=False,
    )

    use_approval_route_entry = fields.Selection(
        string="Use Approval Route for Journal Entries",
        related='company_id.use_approval_route_entry',
        readonly=False,
    )
