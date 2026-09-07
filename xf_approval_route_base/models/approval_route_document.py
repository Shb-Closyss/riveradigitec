from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, AccessError
from odoo.tools.safe_eval import safe_eval

from . import selection
from odoo.exceptions import ValidationError


class ApprovalRouteDocument(models.AbstractModel):
    _name = 'approval.route.document'
    _description = 'Document Approval'

    _sub_records_o2m_fields = None

    approval_route_id = fields.Many2one(
        string='Approval Route',
        comodel_name='approval.route',
        domain=lambda self: [('model', '=', self._name)],
        copy=False,
    )
    approval_route_stage_ids = fields.One2many(
        string='Approval Stages',
        comodel_name='approval.route.document.stage',
        inverse_name='res_id',
        domain=lambda self: [('res_model', '=', self._name)],
        readonly=True,
    )
    current_approval_stage_id = fields.Many2one(
        string='Current Approval Stage',
        comodel_name='approval.route.document.stage',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
    )
    next_approval_stage_id = fields.Many2one(
        string='Next Approval Stage',
        comodel_name='approval.route.document.stage',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
    )
    is_under_approval = fields.Boolean(
        string='Is Under Approval',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
        help='True if document is waiting approval'
    )
    is_approval_received = fields.Boolean(
        string='Is Approval Received',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
        help='True if document received approval from at least one approver'
    )
    is_fully_approved = fields.Boolean(
        string='Is Fully Approved',
        compute='_compute_approval_stage',
        store=True,
        compute_sudo=True,
        help='True if document received approval from all approvers'
    )
    is_current_approver = fields.Boolean(
        string='Is Current Approver',
        compute='_compute_is_current_approver',
        search='_search_is_current_approver',
    )

    @api.depends('approval_route_stage_ids', 'approval_route_stage_ids.state')
    def _compute_approval_stage(self):
        for record in self:
            stages = record.approval_route_stage_ids
            next_stages = stages.filtered(lambda s: s.state == selection.APPROVAL_STATE_TO_APPROVE)
            record.next_approval_stage_id = next_stages[0] if next_stages else None

            current_stage = stages.filtered(lambda s: s.state == selection.APPROVAL_STATE_PENDING)
            record.current_approval_stage_id = current_stage[0] if current_stage else None

            approved_stages = stages.filtered(lambda s: s.state == selection.APPROVAL_STATE_APPROVED)
            record.is_approval_received = len(approved_stages)

            record.is_under_approval = bool(next_stages or current_stage)
            record.is_fully_approved = record._is_fully_approved()

    def _is_fully_approved(self):
        self.ensure_one()
        return set(self.approval_route_stage_ids.mapped('state')) == {selection.APPROVAL_STATE_APPROVED}

    @api.depends('current_approval_stage_id')
    @api.depends_context('uid')
    def _compute_is_current_approver(self):
        for record in self:
            record.is_current_approver = (
                record.current_approval_stage_id and
                (
                    self.env.user in record.current_approval_stage_id.user_ids
                    or self.env.is_superuser()
                )
            )

    def _search_is_current_approver(self, operator, value):
        user_id = self.env.user.id
        if operator in ('in', 'not in'):
            val = any(value) if isinstance(value, (list, tuple)) else bool(value)
        else:
            val = bool(value)

        is_positive = (operator in ('=', 'in') and val) or (operator in ('!=', 'not in') and not val)
        if is_positive:
            return [('current_approval_stage_id.user_ids', 'in', user_id)]
        else:
            return ['|', ('current_approval_stage_id', '=', False), ('current_approval_stage_id.user_ids', 'not in', user_id)]

    @api.model
    def check_field_access_rights(self, operation, fields):
        if operation == 'write':
            self._check_locked_fields(fields)
        return super(ApprovalRouteDocument, self).check_field_access_rights(operation, fields)

    def _write(self, vals):
        self._check_locked_fields(vals.keys())
        return super(ApprovalRouteDocument, self)._write(vals)

    def _check_locked_fields(self, fields):
        for record in self:
            if not record.is_under_approval and not record.is_approval_received:
                # Skip if the document has not been approved by any approver yet
                continue
            approval_route = record.approval_route_id
            if not approval_route.lock_fields:
                # Skip if the option is disabled
                continue
            locked_fields = set(record.approval_route_id.sudo().locked_fields.mapped('name'))
            if set(fields) & locked_fields:
                reason = ''
                if record.is_approval_received:
                    reason = _(', as approval has been received from one or more approvers.')
                elif record.is_under_approval:
                    reason = _(', as it is currently under approval.')
                msg = [
                    _('The document locking option is enabled in the approval workflow settings.'),
                    _('This document cannot be modified %s') % reason
                ]
                raise AccessError('\n'.join(msg))

    def action_send_activity(self):
        self.ensure_one()
        if not self.next_approval_stage_id or not self.id:
            return
        res_model_id = self.env['ir.model'].sudo()._get_id(self._name)
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        for user in self.next_approval_stage_id.mapped('user_ids.id'):
            self.env['mail.activity'].sudo().create({
                'res_model_id': res_model_id,
                'res_id': self.id,
                'activity_type_id': activity_type_id,
                'summary': 'Approval',
                'user_id': user,
            })

    def _action_approve(self):
        self.action_make_decision(selection.APPROVAL_STATE_APPROVED)

    def _action_reject(self):
        self.action_make_decision(selection.APPROVAL_STATE_REJECTED)

    def action_make_decision(self, decision):
        for record in self:
            approval_stage = record.current_approval_stage_id
            if not record.current_approval_stage_id:
                raise UserError(_('This %s is not under approval!') % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            record.message_post(body=_('%s %s by %s') % (self._description, decision, self.env.user.name))

            if decision == selection.APPROVAL_STATE_APPROVED:
                # If user approved document, state is changed according to approval type (one or all)
                if approval_stage.approval_type == selection.APPROVAL_TYPE_ONE:
                    approval_stage.state = decision
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_ALL:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_DEPT_HEAD_LOGGED_USER:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_DEPT_MANAGER_LOGGED_USER:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_DEPT_HEAD:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_DEPT_REQUESTOR:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_RESPONSIBLE_USER:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
                record.activity_ids.filtered(lambda x: record.env.user.id == x.user_id.id).action_feedback(
                    feedback='Approved')
            elif decision == selection.APPROVAL_STATE_REJECTED:
                # If user rejected document, state is changed as "rejected"
                approval_stage.state = decision

            if record._is_fully_approved():
                record.message_post(body=_('%s was fully approved') % self._description)
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
                record._action_send_to_approve()

    def _action_send_to_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)
            partners = record.next_approval_stage_id.user_ids.mapped('partner_id')
            record.sudo().message_post(body=message_body, partner_ids=partners.ids)
            record.action_send_activity()
            record.next_approval_stage_id.sudo().state = 'pending'

    def _get_globals_dict(self):
        return {
            'self': self,
            'env': self.env,
            'user': self.env.user,
        }

    def compute_custom_condition(self, approval_stage):
        self.ensure_one()
        globals_dict = self._get_globals_dict()
        if not approval_stage.condition_code:
            return True
        try:
            safe_eval(approval_stage.condition_code, globals_dict, mode='exec', nocopy=True)
            return bool(globals_dict['result'])
        except Exception as e:
            raise UserError(_('Wrong condition code defined for %s. Error: %s') % (approval_stage.display_name, e))

    def compute_amount_condition(self, approval_stage):
        self.ensure_one()
        if (not approval_stage.condition_amount_field_id or
                not approval_stage.condition_amount_operator or
                not approval_stage.condition_amount_currency_id):
            return True

        monetary_field = self._fields[approval_stage.condition_amount_field_id.name]
        monetary_currency_field = monetary_field.get_currency_field(self)

        # Convert amount from document to approval stage currency
        amount = self[monetary_currency_field]._convert(
            getattr(self, approval_stage.condition_amount_field_id.name),  # amount from document
            approval_stage.condition_amount_currency_id,  # approval stage currency
            approval_stage.approval_route_id.company_id,
            fields.Date.context_today(self)
        )
        if approval_stage.condition_amount_operator == selection.AMOUNT_TERM_LE_OPERATOR:
            return amount <= approval_stage.condition_amount
        if approval_stage.condition_amount_operator == selection.AMOUNT_TERM_GE_OPERATOR:
            return amount >= approval_stage.condition_amount

        return True

    def compute_m2m_condition(self, approval_stage, relation_type):
        m2m_field = approval_stage[f'condition_{relation_type}_field_id']
        m2m_operator = approval_stage[f'condition_{relation_type}_operator']
        m2m_condition_records = approval_stage[f'condition_{relation_type}_ids']
        if not m2m_field or not m2m_operator or not m2m_condition_records:
            return True

        m2m_records = self[m2m_field.name]

        if m2m_operator == selection.M2M_POSITIVE_TERM_OPERATOR:
            return bool(m2m_records & m2m_condition_records)
        if m2m_operator == selection.M2M_NEGATIVE_TERM_OPERATOR:
            return not bool(m2m_records & m2m_condition_records)

    def _clear_approval_stages(self):
        for record in self:
            if record.approval_route_stage_ids:
                # reset approval stages
                record.approval_route_stage_ids.unlink()

    def unlink(self):
        """Cascade-delete approval stage records when parent document is deleted.
        Since res_id is a Many2oneReference (integer) with no DB-level ondelete,
        orphaned stages would otherwise remain and cause errors in My Approvals."""
        # Collect all stage records linked to these documents before deleting
        stage_model = self.env['approval.route.document.stage']
        for record in self:
            stages = stage_model.sudo().search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
            ])
            stages.unlink()
        return super().unlink()

    def generate_approval_route(self):
        """
        Generate approval route for order
        :return:
        """
        for record in self:
            if not record.approval_route_id:
                continue
            record._clear_approval_stages()

            for approval_stage in record.approval_route_id.sudo().stage_ids:
                if approval_stage.custom_domain:
                    list_condition = eval(approval_stage.custom_domain)
                    list_condition.append(('id', '=', self._origin.id))
                    if 'active' in self.env[self._name]._fields:
                        list_condition.append('|')
                        list_condition.append(('active', '=', True))
                        list_condition.append(('active', '=', False))
                    check_lead = self.env[self._name].search(list_condition)
                    if check_lead:
                        record.add_document_stage(approval_stage)
                        continue
                    else:
                        continue
                if not approval_stage.use_custom_conditions:
                    # If custom conditions are not set, just add approval stage for the document
                    record.add_document_stage(approval_stage)
                    continue
                # Else, compute if the approval stage is applicable for that document
                amount_condition = record.compute_amount_condition(approval_stage)
                if not amount_condition:
                    continue
                m2m_condition = True
                for m2m_relation_type in approval_stage._m2m_relation_types:
                    m2m_condition = record.compute_m2m_condition(approval_stage, m2m_relation_type)
                    if not m2m_condition:
                        break
                if not m2m_condition:
                    continue

                custom_condition = record.compute_custom_condition(approval_stage)
                if not custom_condition:
                    continue
                # If all custom conditions are met, add approval stage for the document
                record.add_document_stage(approval_stage)

    def add_document_stage(self, approval_stage):
        """
        Add approval stage for the document
        :param object approval_stage: approval.route.stage
        :return:
        """
        user_ids = approval_stage.computed_user_ids.ids
        if approval_stage.approval_type == 'department_head_logged_user':
            if self._name == 'hr.expense':
                user_ids.append(self.employee_id.hod_id.user_id.id)
            else:
                user_ids.append(self.env.user.employee_id.hod_id.user_id.id)
        if approval_stage.approval_type == 'dept_manager_logged_user':
            if self._name == 'hr.expense':
                user_ids.append(self.employee_id.parent_id.user_id.id)
            else:
                user_ids.append(self.env.user.employee_id.parent_id.user_id.id)
        if approval_stage.approval_type == 'department_requestor':
            employee = getattr(self, approval_stage.condition_requestor_field_id.name)
            if not employee:
                raise ValidationError('Please select the Requestor in Other Info tab')
            if employee:
                if employee._name == 'res.users':
                    if not employee.employee_id.hod_id:
                        raise ValidationError('HOD is not set for this Requestor')
                else:
                    if not employee.hod_id:
                        raise ValidationError('HOD is not set for this Requestor')
            user_ids.append(
                employee.hod_id.user_id.id if employee._name != 'res.users' else employee.employee_id.hod_id.user_id.id)
        if approval_stage.approval_type == 'responsible_user':
            employee = getattr(self, approval_stage.condition_requestor_field_id.name)
            if employee:
                if employee._name == 'res.users':
                    user_ids.append(employee.employee_id.hod_id.user_id.id)
                elif employee._name == 'hr.employee':
                    user_ids.append(employee.hod_id.user_id.id)

        self.ensure_one()
        self.env['approval.route.document.stage'].create({
            'res_model': self._name,
            'res_id': self.id,
            'sequence': approval_stage.sequence,
            'name': approval_stage.name,
            'user_ids': [Command.set(user_ids)],
            'approval_type': approval_stage.approval_type,
            'state': selection.APPROVAL_STATE_TO_APPROVE,
        })


class ApprovalRouteDocumentStage(models.Model):
    _name = 'approval.route.document.stage'
    _description = 'Document Approval Stage'
    _order = 'sequence, id'

    res_model = fields.Char(
        string='Related Document Model Name',
        required=True,
        index=True,
    )
    res_id = fields.Many2oneReference(
        string='Related Document ID',
        required=True,
        index=True,
        model_field='res_model',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=1,
    )
    name = fields.Char(
        string='Stage',
        required=True,
    )
    user_ids = fields.Many2many(
        string='Approvers',
        comodel_name='res.users',
        relation='approval_route_document_stage_users',
        column1='document_stage_id',
        column2='user_id',
    )
    approval_type = fields.Selection(
        string='Approval Type',
        selection=selection.APPROVAL_TYPES,
        default=selection.APPROVAL_TYPE_ONE,
    )
    decisions = fields.Json(
        string='Decisions (Serialized)',
    )
    decisions_summary = fields.Text(
        string='Decisions (Summary)',
        compute='_compute_decisions_summary',
    )
    state = fields.Selection(
        string='Status',
        selection=selection.APPROVAL_STATES,
        readonly=True,
        required=True,
        default=selection.APPROVAL_STATE_TO_APPROVE,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor/Customer',
        compute='_compute_document_details',
    )
    total_amt = fields.Float(
        string='Total Value',
        compute='_compute_document_details',
    )
    is_reference = fields.Boolean(default=False, compute='check_reference', store=True)
    approver_comment = fields.Text(
        string='Approver Comment',
        help='Internal note or comment added by the approver. '
             'Visible in the My Approvals list and on the approval stage.',
    )
    document_type_label = fields.Char(
        string='Document Type',
        compute='_compute_document_type_label',
        store=True,
    )

    # Friendly display names for known models
    _MODEL_LABEL_MAP = {
        'account.move':      'Invoice / Bill',
        'purchase.order':    'Purchase Order',
        'sale.order':        'Sales Order',
        'hr.expense':        'Expense',
        'hr.expense.sheet':  'Expense Report',
        'stock.picking':     'Transfer',
        'res.partner':       'Contact',
        'account.payment':   'Payment',
    }

    @api.depends('res_model')
    def _compute_document_type_label(self):
        for rec in self:
            rec.document_type_label = self._MODEL_LABEL_MAP.get(
                rec.res_model, rec.res_model or ''
            )

    @api.depends('res_id', 'res_model')
    def check_reference(self):
        """True when the parent document no longer exists (orphaned stage)."""
        for rec in self:
            if not rec.res_id or not rec.res_model:
                rec.is_reference = True
                continue
            try:
                exists = self.env[rec.res_model].sudo().with_context(
                    active_test=False
                ).search_count([('id', '=', rec.res_id)])
                rec.is_reference = not bool(exists)
            except Exception:
                rec.is_reference = True

    @api.depends('res_model', 'res_id')
    def _compute_document_details(self):
        for rec in self:
            partner = False
            total = 0.0
            if rec.res_model and rec.res_id:
                try:
                    doc = self.env[rec.res_model].sudo().browse(rec.res_id)
                    if doc.exists():
                        # Determine partner
                        if rec.res_model == 'res.partner':
                            partner = doc
                        elif getattr(doc, 'partner_id', False):
                            partner = doc.partner_id
                        elif getattr(doc, 'employee_id', False):
                            partner = getattr(doc.employee_id, 'work_contact_id', False) or getattr(doc.employee_id.user_id, 'partner_id', False)

                        # Determine total amount
                        if hasattr(doc, 'amount_total'):
                            total = doc.amount_total
                        elif hasattr(doc, 'total_amount'):
                            total = doc.total_amount
                        elif hasattr(doc, 'amount'):
                            total = doc.amount
                except Exception:
                    pass
            rec.partner_id = partner
            rec.total_amt = total

    def fetch_total_amt_from_model(self):
        self._compute_document_details()

    def action_approve_stage(self):
        """Approve the document stage directly from the approval list/kanban line."""
        for stage in self:
            if stage.state not in ('pending', 'to approve'):
                continue
            if stage.res_model and stage.res_id:
                doc = self.env[stage.res_model].browse(stage.res_id)
                if doc.exists():
                    if hasattr(doc, 'action_approve'):
                        doc.action_approve()
                    elif hasattr(doc, '_action_approve'):
                        doc._action_approve()

    def action_reject_stage(self):
        """Trigger rejection wizard for the document stage directly from line/kanban."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_("Related document reference is missing."))

        res_model_wiz = 'reject.reason' if 'reject.reason' in self.env else 'xf.reject.reason'
        return {
            'name': _('Reject Approval'),
            'type': 'ir.actions.act_window',
            'res_model': res_model_wiz,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self.res_model,
                'default_res_id': self.res_id,
            }
        }

    def open_record(self):
        """Open the parent document. If it no longer exists, clean up and warn."""
        self.ensure_one()
        if not self.res_id or not self.res_model:
            self.sudo().unlink()
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'type': 'warning', 'message': 'The related document no longer exists and has been removed from the approval queue.', 'sticky': False}}
        try:
            exists = self.env[self.res_model].sudo().with_context(
                active_test=False
            ).search_count([('id', '=', self.res_id)])
        except Exception:
            exists = 0
        if not exists:
            self.sudo().unlink()
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'type': 'warning', 'message': 'The related document no longer exists and has been removed from the approval queue.', 'sticky': False}}
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'self'
        }

    def bulk_approve(self):
        # First, purge any orphaned stages (parent document deleted)
        orphaned = self.filtered(lambda x: x.is_reference)
        if orphaned:
            orphaned.sudo().unlink()
            self = self - orphaned  # noqa: PLW0642

        apart_from_pending = self.filtered(lambda x: x.state in ['to approve', 'approved', 'rejected'])
        if apart_from_pending:
            raise ValidationError('You can only select Pending Approval')
        pending_approve = self.filtered(lambda x: x.state in ['pending'])
        for p_approve in pending_approve:
            try:
                res_record = self.env[p_approve.res_model].with_context(
                    active_test=False
                ).browse(p_approve.res_id)
                if res_record.exists():
                    if hasattr(res_record, 'action_approve'):
                        res_record.action_approve()
                    else:
                        res_record._action_approve()
                else:
                    p_approve.sudo().unlink()
            except Exception:
                p_approve.sudo().unlink()

    @api.depends('decisions')
    def _compute_decisions_summary(self):
        for stage in self:
            summary = ''
            if isinstance(stage.decisions, dict):
                # If there is at least one decision generate user-friendly summary
                for user_id, decision in stage.decisions.items():
                    user = stage.user_ids.filtered_domain([('id', '=', int(user_id))])
                    if not user:
                        user_admin = self.env['res.users'].browse(int(user_id))
                        user = user_admin
                    summary += f'* {user.name}: {decision} \n'
            stage.decisions_summary = summary

    def action_purge_orphaned(self):
        """Manually delete all approval stage records whose parent document
        no longer exists. Can be triggered from the list header button."""
        orphaned = self.search([]).filtered(lambda r: r.is_reference)
        count = len(orphaned)
        if orphaned:
            orphaned.sudo().unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if count else 'info',
                'message': f'{count} orphaned approval record(s) removed.' if count else 'No orphaned records found.',
                'sticky': False,
            }
        }

    @api.model
    def _cron_purge_orphaned_stages(self):
        """Scheduled action: remove approval.route.document.stage records
        whose parent document has been deleted."""
        all_stages = self.sudo().search([])
        orphaned = all_stages.filtered(lambda r: r.is_reference)
        if orphaned:
            orphaned.unlink()
