# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dispatch_management_email = fields.Char(
        string='Management Dispatch Email(s)',
        config_parameter='rivera.dispatch_management_email',
        help='Comma-separated email addresses of management to receive the daily dispatch report.',
    )
