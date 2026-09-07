# -*- coding: utf-8 -*-

from odoo import fields, models, api

from . import selection


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        selection=selection.USE_APPROVAL_ROUTE,
        default=selection.USE_APPROVAL_ROUTE_OPTIONAL,
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route = fields.Selection(
        string='Use Approval Route',
        related='company_id.use_approval_route',
        readonly=False,
    )

    approval_role_count = fields.Integer(
        string='Count Predefined Roles',
        compute='_compute_approval_role_count',
    )

    approval_route_count = fields.Integer(
        string='Count Approval Routes',
        compute='_compute_approval_route_count',
    )

    @api.depends('company_id')
    def _compute_approval_role_count(self):
        for record in self:
            count = self.env['approval.role'].search_count([('company_id', '=', record.company_id.id)])
            record.approval_role_count = count

    @api.depends('company_id')
    def _compute_approval_route_count(self):
        for record in self:
            count = self.env['approval.route'].search_count([('company_id', '=', record.company_id.id)])
            record.approval_route_count = count
