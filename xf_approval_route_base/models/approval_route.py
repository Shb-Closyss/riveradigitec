# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.models import LOG_ACCESS_COLUMNS


class ApprovalRoute(models.Model):
    _name = 'approval.route'
    _description = 'Approval Route'

    def _internal_fields(self):
        internal_fields = ['id']
        internal_fields += LOG_ACCESS_COLUMNS
        internal_fields += ['message_follower_ids', 'message_ids', 'message_main_attachment_id', 'website_message_ids']
        internal_fields += ['activity_ids']
        return internal_fields

    def _locked_fields_domain(self):
        return "[('store', '=', True), ('model_id', '=', model_id), ('name', 'not in', %s)]" % self._internal_fields()

    active = fields.Boolean(
        string='Active',
        default=True,
    )
    name = fields.Char(
        string='Name',
        required=True,
    )
    model_id = fields.Many2one(
        string='Applicable for',
        comodel_name='ir.model',
        required=True,
        index=True,
        ondelete='cascade',
        help='Record model which the approval route applicable for',
    )
    model = fields.Char(
        string='Model Name',
        related='model_id.model',
        compute_sudo=True,
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        index=True,
    )
    user_id = fields.Many2one(
        string='Responsible User',
        comodel_name='res.users',
        default=lambda self: self.env.user,
        required=True,
        index=True,
    )
    stage_ids = fields.One2many(
        string='Approval Stages',
        comodel_name="approval.route.stage",
        inverse_name='approval_route_id',
        copy=True,
    )
    can_edit = fields.Boolean(
        string='Can Edit',
        compute='_compute_can_edit',
    )
    lock_fields = fields.Boolean(
        string='Lock Fields',
        default=False,
    )
    locked_fields = fields.Many2many(
        string='Locked Fields',
        comodel_name='ir.model.fields',
        relation='approval_route_locked_fields',
        column1='approval_route_id',
        column2='field_id',
        domain=lambda self: self._locked_fields_domain(),
        help="""
        Here you need to specify document fields that need to be locked for editing 
        after being sent for approval or 
        after receiving approval from at least one participant
        """
    )
    department_ids = fields.Many2many('hr.department', string='Department')
    move_type = fields.Selection(selection=[
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
        ],
        string='Type')
    custom_domain = fields.Char(string='Custom Domain')

    @api.constrains('lock_fields', 'locked_fields')
    def _check_locked_fields(self):
        for route in self:
            if route.lock_fields and not route.locked_fields:
                raise ValidationError(_('Please specify at least one field to lock!'))

    def _can_edit(self):
        self.ensure_one()
        is_user = self.env.user.has_group('xf_approval_route_base.group_approval_route_user')
        is_manager = self.env.user.has_group('xf_approval_route_base.group_approval_route_manager')
        return is_manager or (is_user and self.user_id == self.env.user) or self.env.is_superuser()

    @api.depends('user_id')
    def _compute_can_edit(self):
        for route in self:
            route.can_edit = route._can_edit()

    # @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(ApprovalRoute, self).copy(default=default)

    def add_stage(self):
        self.ensure_one()
        max_sequence = max(self.stage_ids.mapped('sequence')) if self.stage_ids else 0
        add_context = {'default_sequence': max_sequence + 1}
        return self.env['approval.route.stage'].get_stage_act_window_form(self, add_context=add_context)
