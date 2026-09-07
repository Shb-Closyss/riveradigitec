# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        res = super().action_post()
        self._auto_reconcile_by_payment_reference()
        return res

    def _auto_reconcile_by_payment_reference(self):
        """Auto-reconcile posted payments with invoices based on matching payment reference."""
        for payment in self:
            # Only process inbound customer payments with a memo/reference
            if payment.payment_type != 'inbound' or payment.partner_type != 'customer':
                continue
            if not payment.memo or not payment.partner_id:
                continue

            ref = payment.memo.strip()
            if not ref:
                continue

            # Find posted customer invoices with a matching payment_reference
            invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('payment_reference', '=', ref),
                ('partner_id', '=', payment.partner_id.id),
                ('company_id', '=', payment.company_id.id),
                ('state', '=', 'posted'),
            ])

            # Skip if no match found
            if not invoices:
                continue

            # Skip if multiple invoices share the same reference (ambiguous)
            if len(invoices) > 1:
                _logger.info(
                    "Auto-reconcile skipped for payment %s: multiple invoices found "
                    "with payment reference '%s' for partner %s.",
                    payment.name, ref, payment.partner_id.display_name,
                )
                continue

            invoice = invoices

            # Skip if invoice is already fully reconciled
            if invoice.payment_state in ('paid', 'in_payment', 'reversed'):
                continue

            # Get unreconciled receivable lines from invoice and payment
            invoice_lines = invoice.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
            )
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
            )

            if not invoice_lines or not payment_lines:
                continue

            # Reconcile the receivable lines together
            (invoice_lines + payment_lines).reconcile()

            _logger.info(
                "Auto-reconciled payment %s with invoice %s (ref: '%s').",
                payment.name, invoice.name, ref,
            )
