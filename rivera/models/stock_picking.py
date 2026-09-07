# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    courier_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Courier Partner',
        copy=False,
        help='Courier / transport agency handling the shipment delivery.',
    )
    docket_no = fields.Char(
        string='Docket No.',
        copy=False,
        help='Tracking or docket number provided by the courier partner.',
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Invoice No.',
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
        copy=False,
        help='Related customer invoice for this delivery order.',
    )
    salesperson_id = fields.Many2one(
        comodel_name='res.users',
        string='Salesperson',
        compute='_compute_salesperson_id',
        store=True,
        readonly=False,
        precompute=True,
        help='Salesperson from the related Sales Order.',
    )
    dispatch_email_sent = fields.Boolean(
        string='Dispatch Email Sent',
        copy=False,
        default=False,
        help='Flag indicating whether the dispatch notification has been sent.',
    )

    @api.depends('sale_id.user_id')
    def _compute_salesperson_id(self):
        for picking in self:
            picking.salesperson_id = picking.sale_id.user_id if picking.sale_id else False

    def action_send_dispatch_email(self):
        """Manually send dispatch emails for selected delivery orders."""
        for picking in self:
            if picking.state != 'done':
                raise UserError("Dispatch email can only be sent for validated/done Delivery Orders.")
            if picking.picking_type_code != 'outgoing':
                raise UserError("Dispatch email can only be sent for outgoing Delivery Orders.")

            # Send salesperson email if salesperson exists
            if picking.salesperson_id:
                picking._send_salesperson_dispatch_emails(picking)

            # Send management email
            picking._send_management_dispatch_email(picking)

            picking.dispatch_email_sent = True

    @api.model
    def cron_send_daily_dispatch_emails(self):
        """Scheduled action to send daily dispatch report to management and salespersons."""
        pickings = self.search([
            ('picking_type_code', '=', 'outgoing'),
            ('state', '=', 'done'),
            ('dispatch_email_sent', '=', False),
        ])
        if not pickings:
            _logger.info("Daily dispatch cron: No new dispatched delivery orders found.")
            return

        _logger.info("Daily dispatch cron: Found %d delivery orders to process.", len(pickings))

        # 1. Send consolidated report to Management
        self._send_management_dispatch_email(pickings)

        # 2. Send salesperson-specific dispatch emails
        self._send_salesperson_dispatch_emails(pickings)

        # 3. Mark all as sent to prevent duplicate emails
        pickings.write({'dispatch_email_sent': True})

    def _send_management_dispatch_email(self, pickings):
        """Send daily dispatch report to configured management recipients with PDF attached."""
        if not pickings:
            return

        management_emails = self.env['ir.config_parameter'].sudo().get_param(
            'rivera.dispatch_management_email', ''
        ).strip()

        template = self.env.ref('rivera.mail_template_daily_dispatch_management', raise_if_not_found=False)
        if not template:
            _logger.warning("Mail template 'rivera.mail_template_daily_dispatch_management' not found.")
            return

        company = pickings[0].company_id or self.env.company
        email_to = management_emails or company.email
        if not email_to:
            _logger.warning("No management recipient email configured for daily dispatch report.")
            return

        # Render PDF report
        report_action = self.env.ref('rivera.action_report_daily_dispatch', raise_if_not_found=False)
        attachment_ids = []
        if report_action:
            try:
                pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                    report_action, res_ids=pickings.ids
                )
                attachment = self.env['ir.attachment'].create({
                    'name': f"Daily_Dispatch_Report_{fields.Date.today()}.pdf",
                    'type': 'binary',
                    'raw': pdf_content,
                    'mimetype': 'application/pdf',
                })
                attachment_ids.append(attachment.id)
            except Exception as e:
                _logger.error("Failed to generate PDF for management dispatch report: %s", e)

        ctx = {
            'pickings': pickings,
            'dispatch_date': fields.Date.today().strftime('%d-%m-%Y'),
            'company_name': company.name,
        }

        template.with_context(**ctx).send_mail(
            pickings[0].id,
            force_send=True,
            email_values={
                'email_to': email_to,
                'attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else [],
            },
        )
        _logger.info("Management dispatch report emailed to %s (%d orders).", email_to, len(pickings))

    def _send_salesperson_dispatch_emails(self, pickings):
        """Group pickings by salesperson and send each salesperson only their relevant orders."""
        if not pickings:
            return

        template = self.env.ref('rivera.mail_template_daily_dispatch_salesperson', raise_if_not_found=False)
        if not template:
            _logger.warning("Mail template 'rivera.mail_template_daily_dispatch_salesperson' not found.")
            return

        report_action = self.env.ref('rivera.action_report_daily_dispatch', raise_if_not_found=False)

        # Group by salesperson
        salesperson_map = {}
        for picking in pickings:
            sp = picking.salesperson_id
            if sp and (sp.email or sp.partner_id.email):
                salesperson_map.setdefault(sp, self.env['stock.picking'])
                salesperson_map[sp] |= picking

        for salesperson, sp_pickings in salesperson_map.items():
            email_to = salesperson.email or salesperson.partner_id.email
            if not email_to:
                continue

            attachment_ids = []
            if report_action:
                try:
                    pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                        report_action, res_ids=sp_pickings.ids
                    )
                    attachment = self.env['ir.attachment'].create({
                        'name': f"Dispatch_Report_{salesperson.name}_{fields.Date.today()}.pdf",
                        'type': 'binary',
                        'raw': pdf_content,
                        'mimetype': 'application/pdf',
                    })
                    attachment_ids.append(attachment.id)
                except Exception as e:
                    _logger.error("Failed to generate PDF for salesperson %s: %s", salesperson.name, e)

            company = sp_pickings[0].company_id or self.env.company
            ctx = {
                'salesperson': salesperson,
                'pickings': sp_pickings,
                'dispatch_date': fields.Date.today().strftime('%d-%m-%Y'),
                'company_name': company.name,
            }

            template.with_context(**ctx).send_mail(
                sp_pickings[0].id,
                force_send=True,
                email_values={
                    'email_to': email_to,
                    'attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else [],
                },
            )
            _logger.info("Salesperson dispatch email sent to %s (%d orders).", email_to, len(sp_pickings))
