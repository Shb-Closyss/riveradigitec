# -*- coding: utf-8 -*-
from odoo import fields, models


class ApprovalRole(models.Model):
    _name = 'approval.role'
    _description = 'Approval Role'

    active = fields.Boolean(
        string='Active',
        default=True,
    )
    name = fields.Char(
        string='Position/Role',
        required=True,
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        index=True,
        ondelete='cascade',
    )
    user_ids = fields.Many2many(
        string='User(s)',
        comodel_name='res.users',
        relation='approval_route_approver_users',
        column1='approver_id',
        column2='user_id',
        required=True,
    )
