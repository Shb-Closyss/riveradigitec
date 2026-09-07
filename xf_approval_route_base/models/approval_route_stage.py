# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from . import selection


class ApprovalRouteStageConditionCode(models.AbstractModel):
    _name = 'approval.route.stage.condition.code'
    _description = 'Approval Route Stage Condition Code'

    condition_code = fields.Text(
        string='Custom Condition Code',
        help='You can enter python expression to define custom condition'
    )

    def _humanize_code_condition(self):
        if self.condition_code:
            return _('* Document meets custom conditions in Python code')


class ApprovalRouteStageConditionRelation(models.AbstractModel):
    _name = 'approval.route.stage.condition.relation'
    _description = 'Approval Route Stage Condition Relation'

    def _humanize_m2m_condition(self, relation_type):
        relation_field_name = f'condition_{relation_type}_field_id'
        relation_field = getattr(self, relation_field_name)
        m2m_field_name = f'condition_{relation_type}_ids'
        m2m_operator = getattr(self, f'condition_{relation_type}_operator')
        m2m_values = getattr(self, m2m_field_name)
        if m2m_operator and m2m_values:
            m2m_summary = '%s (%s): %s' % (
                self._fields[m2m_field_name].string,
                relation_field.field_description,
                ', '.join(m2m_values.mapped('display_name'))
            )
            if m2m_operator == selection.M2M_POSITIVE_TERM_OPERATOR:
                return _('* Document is associated with selected %s') % m2m_summary
            if m2m_operator == selection.M2M_NEGATIVE_TERM_OPERATOR:
                return _('* Document is not associated with selected %s') % m2m_summary


class ApprovalRouteStageConditionPartner(models.AbstractModel):
    _name = 'approval.route.stage.condition.partner'
    _inherit = 'approval.route.stage.condition.relation'
    _description = 'Approval Route Stage Condition Partner'

    condition_partner_field_id = fields.Many2one(
        string='Partner Field',
        comodel_name='ir.model.fields',
    )
    condition_partner_operator = fields.Selection(
        string='Partner Operator',
        selection=selection.M2M_TERM_OPERATORS,
    )
    condition_partner_ids = fields.Many2many(
        string='Partners',
        comodel_name='res.partner',
        relation='approval_route_stage_condition_partners',
        column1='condition_id',
        column2='partner_id',
    )
    condition_requestor_field_id = fields.Many2one(string='Requestor',comodel_name='ir.model.fields')

    @api.onchange('condition_partner_field_id')
    def _onchange_condition_partner_field(self):
        if not self.condition_partner_field_id:
            self.condition_partner_operator = False
            self.condition_partner_ids = False


class ApprovalRouteStageConditionCountry(models.AbstractModel):
    _name = 'approval.route.stage.condition.country'
    _inherit = 'approval.route.stage.condition.relation'
    _description = 'Approval Route Stage Condition Country'

    condition_country_field_id = fields.Many2one(
        string='Country Field',
        comodel_name='ir.model.fields',
    )
    condition_country_operator = fields.Selection(
        string='Country Operator',
        selection=selection.M2M_TERM_OPERATORS,
    )
    condition_country_ids = fields.Many2many(
        string='Countries',
        comodel_name='res.country',
        relation='approval_route_stage_condition_countries',
        column1='condition_id',
        column2='country_id',
    )

    @api.onchange('condition_company_field_id')
    def _onchange_condition_company_field(self):
        if not self.condition_company_field_id:
            self.condition_company_operator = False
            self.condition_company_ids = False


class ApprovalRouteStageConditionCompany(models.AbstractModel):
    _name = 'approval.route.stage.condition.company'
    _inherit = 'approval.route.stage.condition.relation'
    _description = 'Approval Route Stage Condition Company'

    condition_company_field_id = fields.Many2one(
        string='Company Field',
        comodel_name='ir.model.fields',
    )
    condition_company_operator = fields.Selection(
        string='Company Operator',
        selection=selection.M2M_TERM_OPERATORS,
    )
    condition_company_ids = fields.Many2many(
        string='Companies',
        comodel_name='res.company',
        relation='approval_route_stage_condition_companies',
        column1='condition_id',
        column2='company_id',
    )

    @api.onchange('condition_country_field_id')
    def _onchange_condition_country_field(self):
        if not self.condition_country_field_id:
            self.condition_country_operator = False
            self.condition_country_ids = False


class ApprovalRouteStageConditionProduct(models.AbstractModel):
    _name = 'approval.route.stage.condition.product'
    _inherit = 'approval.route.stage.condition.relation'
    _description = 'Approval Route Stage Condition Product'

    condition_product_field_id = fields.Many2one(
        string='Product Field',
        comodel_name='ir.model.fields',
    )
    condition_product_operator = fields.Selection(
        string='Product Operator',
        selection=selection.M2M_TERM_OPERATORS,
    )
    condition_product_ids = fields.Many2many(
        string='Products',
        comodel_name='product.product',
        relation='approval_route_stage_condition_products',
        column1='condition_id',
        column2='product_id',
    )

    @api.onchange('condition_product_field_id')
    def _onchange_condition_product_field(self):
        if not self.condition_product_field_id:
            self.condition_product_operator = False
            self.condition_product_ids = False


class ApprovalRouteStageConditionAnalyticAccount(models.AbstractModel):
    _name = 'approval.route.stage.condition.analytic.account'
    _inherit = 'approval.route.stage.condition.relation'
    _description = 'Approval Route Stage Condition Analytic Account'

    condition_analytic_account_field_id = fields.Many2one(
        string='Analytic Account Field',
        comodel_name='ir.model.fields',
    )
    condition_analytic_account_operator = fields.Selection(
        string='Analytic Account Operator',
        selection=selection.M2M_TERM_OPERATORS,
    )
    condition_analytic_account_ids = fields.Many2many(
        string='Analytic Accounts',
        comodel_name='account.analytic.account',
        relation='approval_route_stage_condition_analytic_accounts',
        column1='condition_id',
        column2='analytic_account_id',
    )

    @api.onchange('condition_analytic_account_field_id')
    def _onchange_condition_analytic_account_field(self):
        if not self.condition_analytic_account_field_id:
            self.condition_analytic_account_operator = False
            self.condition_analytic_account_ids = False


class ApprovalRouteStageConditionAmount(models.AbstractModel):
    _name = 'approval.route.stage.condition.amount'
    _description = 'Approval Route Stage Condition Amount'

    condition_amount_field_id = fields.Many2one(
        string='Amount Field',
        comodel_name='ir.model.fields',
    )
    condition_amount_operator = fields.Selection(
        string='Amount Operator',
        selection=selection.AMOUNT_TERM_OPERATORS,
    )
    condition_amount = fields.Monetary(
        string="Amount",
        currency_field='condition_amount_currency_id',
        help="""Amount (included) for which approval is required""",
    )
    condition_amount_currency_id = fields.Many2one(
        string="Currency",
        comodel_name='res.currency',
        help='Utility field to express threshold currency',
    )

    @api.onchange('condition_amount_field_id')
    def _onchange_condition_amount_field(self):
        if not self.condition_amount_field_id:
            self.condition_amount_operator = False
            self.condition_amount = False
            self.condition_amount_currency_id = False

    def _humanize_amount_condition(self):
        if self.condition_amount_field_id and self.condition_amount_operator and self.condition_amount_currency_id:
            return _('* %s %s %s %s') % (self.condition_amount_field_id.field_description,
                                         self.condition_amount_operator,
                                         self.condition_amount,
                                         self.condition_amount_currency_id.name)


class ApprovalRouteStage(models.Model):
    _name = 'approval.route.stage'
    _inherit = [
        'approval.route.stage.condition.amount',
        'approval.route.stage.condition.code',
        'approval.route.stage.condition.partner',
        'approval.route.stage.condition.company',
        'approval.route.stage.condition.country',
        'approval.route.stage.condition.product',
        'approval.route.stage.condition.analytic.account',
    ]
    _description = 'Approval Route Stage'
    _order = 'sequence asc, id'

    _m2m_relation_types = ['partner', 'country', 'company', 'product', 'analytic_account']

    sequence = fields.Integer(
        string='Sequence',
        default=1,
    )
    approval_route_id = fields.Many2one(
        string='Approval Route',
        comodel_name='approval.route',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        related='approval_route_id.company_id',
        readonly=True,
    )
    model_id = fields.Many2one(
        string='Applicable for',
        comodel_name='ir.model',
        related='approval_route_id.model_id',
        readonly=True,
        help='Record model which the approval route applicable for',
    )
    can_edit = fields.Boolean(
        string='Can Edit',
        compute='_compute_can_edit',
    )
    name = fields.Char(
        string='Stage',
        required=True,
    )
    computed_user_ids = fields.Many2many(
        string='Approvers',
        comodel_name='res.users',
        relation='approval_route_stage_computed_users',
        column1='stage_id',
        column2='user_id',
        compute='_compute_user_ids',
        store=True,
    )
    custom_user_ids = fields.Many2many(
        string='Approvers (Custom)',
        comodel_name='res.users',
        relation='approval_route_stage_users',
        column1='stage_id',
        column2='user_id',
    )
    approval_role_id = fields.Many2one(
        string='Approvers (Predefined)',
        comodel_name='approval.role',
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    approval_type = fields.Selection(
        string='Approval Type',
        selection=selection.APPROVAL_TYPES,
        default=selection.APPROVAL_TYPE_ONE,
    )
    # Condition Fields
    use_custom_conditions = fields.Boolean(
        string='Use Custom Conditions',
        help='If enabled, you will be able to set custom conditions to add stage to approval route dynamically'
    )
    condition_summary = fields.Text(
        string='Condition Summary',
        compute='_compute_condition_summary',
        compute_sudo=True,
    )
    department_id = fields.Many2one('hr.department')
    custom_domain = fields.Char(string='Custom Domain')
    model = fields.Char(
        string='Model Name',
        related='model_id.model',
        compute_sudo=True,
        store=True,
        readonly=True,
    )


    # Custom Code --Sanmeet
    @api.onchange('department_id')
    def fetch_department_manager(self):
        for stage in self:
            if stage.department_id:
                stage.custom_user_ids = [(4,stage.department_id.manager_id.user_id.id)]


    @api.onchange('approval_type')
    def empty_data_for_type(self):
        for stage in self:
            if stage.approval_type == 'department_head_logged_user':
                stage.custom_user_ids = False
                stage.department_id = False
            if stage.approval_type == 'dept_manager_logged_user':
                stage.custom_user_ids = False
                stage.department_id = False
            if stage.approval_type == 'department_requestor':
                stage.custom_user_ids = False
                stage.department_id = False
    # Ends Here

    def _compute_can_edit(self):
        for stage in self:
            stage.can_edit = stage.approval_route_id._can_edit()

    @api.depends('custom_user_ids', 'approval_role_id')
    def _compute_user_ids(self):
        for stage in self:
            users = stage.custom_user_ids
            if stage.approval_role_id:
                users |= stage.approval_role_id.user_ids
            stage.computed_user_ids = users

    @api.constrains('computed_user_ids')
    def _check_computed_user_ids(self):
        for stage in self:
            if stage.approval_type in ['one','all','department_head']:
                if not stage.computed_user_ids:
                    raise ValidationError(_('Please set at least one approver!'))

    @api.depends('use_custom_conditions')
    def _compute_condition_summary(self):
        for stage in self:
            if not stage.use_custom_conditions:
                stage.condition_summary = _('Custom conditions are disabled')
            else:
                summary_lines = [stage._humanize_amount_condition()]
                for m2m_relation_type in self._m2m_relation_types:
                    m2m_line = stage._humanize_m2m_condition(m2m_relation_type)
                    if m2m_line:
                        summary_lines.append(m2m_line)
                summary_lines.append(stage._humanize_code_condition())

                summary_lines = list(filter(None, summary_lines))
                if summary_lines:
                    stage.condition_summary = '\n'.join([_('Apply if:')] + summary_lines)
                else:
                    stage.condition_summary = _('No additional conditions are set')

    def edit_stage(self):
        self.ensure_one()
        return self.get_stage_act_window_form(self.approval_route_id, self.id)

    def get_stage_act_window_form(self, approval_route, res_id=None, add_context=None):
        view = self.env.ref('xf_approval_route_base.approval_route_stage_form')
        act_window_context = {
            'default_approval_route_id': approval_route.id,
            'approval_route_model': approval_route.model,
        }
        if add_context:
            act_window_context.update(**add_context)
        return {
            'name': _('Additional Configuration for Approval Stage'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': view.model,
            'res_id': res_id,
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': act_window_context,
        }
