# -*- coding: utf-8 -*-
from odoo import fields, models


class HelpdeskReportedIssue(models.Model):
    _name = 'helpdesk.reported.issue'
    _description = 'Helpdesk Reported Issue Master'
    _order = 'sequence, name'

    name = fields.Char(string='Issue Name', required=True, translate=True)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string='Sequence', default=10)
