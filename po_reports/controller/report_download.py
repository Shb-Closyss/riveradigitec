import io
from io import BytesIO
import json
import pandas as pd
from odoo.http import request
import xlsxwriter
from odoo.http import content_disposition, request, Controller
from odoo import http
import ast
import logging
_logger = logging.getLogger(__name__)


class DownloadReport(Controller):
    font = "Arial"

    @staticmethod
    def compute_taxes(invoice_line):
        tax_val = dict()
        price_unit = invoice_line.price_unit * (1.0 - (invoice_line.discount or 0.0) / 100.0)
        for tax in invoice_line.tax_ids:
            taxes = tax.compute_all(price_unit, invoice_line.currency_id, invoice_line.quantity,
                                    product=invoice_line.product_id, partner=invoice_line.partner_id)
            for tx in taxes['taxes']:
                name = tx.get('name')
                amount = tx.get('amount')
                tax_val.update({name: amount})
        return tax_val

    @staticmethod
    def get_company_details(company_id):
        return request.env['res.company'].search([('id', '=', company_id)]).name

    @staticmethod
    def get_partner_state(move, partner):
        if partner:
            if partner.state_id:
                return partner.state_id.name or ''
            if partner.commercial_partner_id and partner.commercial_partner_id.state_id:
                return partner.commercial_partner_id.state_id.name or ''
            if partner.parent_id and partner.parent_id.state_id:
                return partner.parent_id.state_id.name or ''
        if move and hasattr(move, 'l10n_in_state_id') and move.l10n_in_state_id:
            return move.l10n_in_state_id.name or ''
        return ''

    # styles
    @staticmethod
    def title_format(workbook):
        return workbook.add_format({
            'font_size': 14,
            'font': DownloadReport.font,
            'bold': 1,
            'align': 'center',
            'valign': 'vcenter'})

    @staticmethod
    def txt_font(workbook):
        return workbook.add_format({'bold': 1, 'bg_color': '#ccccff', })

    @staticmethod
    def txt_font2(workbook):
        return workbook.add_format({'bg_color': '#ccccff', })

    @staticmethod
    def txt_font3(workbook):
        return workbook.add_format({'bold': 1, })

    @staticmethod
    def no_data_found():
        fp = io.BytesIO(b'No Data Found')
        with open('no_data_found.txt', 'wb') as f:
            f.write(fp.getbuffer())
        out = fp.getvalue()
        pdfhttpheaders = [('Content-Type', 'application/octet-stream'),
                          ('Content-Disposition', content_disposition(f"No Data Found.txt"))]
        return request.make_response(out, headers=pdfhttpheaders)

    @staticmethod
    def decorate_worksheet(worksheet, df):
        columns = df.columns
        max_width = 50
        for pos, col in enumerate(columns):
            max_str = max(df[col].apply(str).str.len()) + 5
            col_name_len = len(col) + 5
            col_size = max_width if max_str > max_width else col_name_len if max_str < col_name_len else max_str
            worksheet.set_column(pos, pos, col_size)
        worksheet.freeze_panes(2, 0)

    @staticmethod
    def dataframe_operations(data, sheet_name, writer):
        if data:
            df = pd.DataFrame(data)
            sort_column = df.columns[0]
            nan_value = float("NaN")
            df.replace("", nan_value, inplace=True)
            cols_to_preserve = {'HSN Code'}
            drop_cols = [col for col in df.columns if df[col].isna().all() and col not in cols_to_preserve]
            df.drop(columns=drop_cols, inplace=True)
            df.sort_values(by=sort_column, inplace=True)
            df.loc['Column_Total'] = df.sum(numeric_only=True, axis=0)
            df.to_excel(writer, index=False, startrow=1, sheet_name=sheet_name)
            DownloadReport.decorate_worksheet(writer.sheets[sheet_name], df)

    @staticmethod
    def create_summary_sheet(writer):
        workbook = writer.book
        summary_sheet = workbook.add_worksheet('Summary')
        return summary_sheet

    @staticmethod
    def detail_sales_register(start_date, end_date, invoice_data, company_id, *args, **kwargs):
        fp = BytesIO()
        writer = pd.ExcelWriter(fp, engine='xlsxwriter')
        summary_sheet = DownloadReport.create_summary_sheet(writer)

        # global tot_qty
        # tot_qty = []

        def get_detailed_sales_data(invoices, sheet_name):
            data_rows = []
            gst_data = {}
            # tot_qty = []
            for invoice_line in invoices.invoice_line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_note')):
                partner_id = invoice_line.move_id.partner_id
                un_tax_amt = invoice_line.move_id.amount_untaxed
                total_amt = invoice_line.move_id.amount_total
                sign = -1 if invoice_line.move_id.move_type == 'out_invoice' else 1
                data = {'Journal': invoice_line.move_id.journal_id.name,
                        'Invoice NO': invoice_line.move_id.name,
                        'Invoice Date': invoice_line.move_id.date.strftime('%d-%m-%Y') if invoice_line.move_id.date else '',
                        'Salesperson': invoice_line.move_id.invoice_user_id.name,
                        'Parent Company': invoice_line.company_id.parent_id.name if invoice_line.company_id.parent_id.name else '-',
                        'Company': invoice_line.company_id.name,
                        'Customer': partner_id.name if partner_id.name else partner_id.parent_id.name,
                        'Customer State': DownloadReport.get_partner_state(invoice_line.move_id, partner_id),
                        'Contact Tags': ', '.join(partner_id.category_id.mapped('name')) if partner_id.category_id else '',
                        # 'Party Code': partner_id.code,
                        # 'Code': partner_id.code,
                        'GST NO': invoice_line.partner_id.vat,
                        'PAN': invoice_line.partner_id.l10n_in_pan_entity_id.name,
                        # 'Broker Code': partner_id.broker_id.code,
                        # 'Broker Name': partner_id.broker_id.name,
                        'Product Code': invoice_line.product_id.default_code,
                        'Product': invoice_line.product_id.name,
                        'Product Tags': ', '.join(invoice_line.product_id.product_tag_ids.mapped('name')) if invoice_line.product_id.product_tag_ids else '',
                        'HSN Code': getattr(invoice_line, 'l10n_in_hsn_code', False) or getattr(invoice_line, 'hsn_code', False) or (invoice_line.product_id and (getattr(invoice_line.product_id, 'l10n_in_hsn_code', False) or getattr(invoice_line.product_id, 'hsn_code', False))) or '',
                        # 'Scheme': invoice_line.scheme_id.name if invoice_line.scheme_id else '',
                        'Sale Order': invoice_line.move_id.invoice_origin if invoice_line.move_id.invoice_origin else '',
                        'Sale Order Date': (invoice_line.sale_line_ids.order_id[:1].date_order.strftime('%d-%m-%Y') if invoice_line.sale_line_ids and invoice_line.sale_line_ids.order_id[:1].date_order else '') if invoice_line.sale_line_ids else '',
                        'Category': invoice_line.product_id.categ_id.name,
                        'Bill Ref': invoice_line.ref,
                        'Account': invoice_line.account_id.display_name,
                        'UOM': invoice_line.product_uom_id.name,
                        'Quantity': invoice_line.quantity, 'Currency': invoice_line.currency_id.name,
                        'Unit Price': invoice_line.price_unit,
                        'Discount': invoice_line.discount, 'Price Subtotal(In Currency)': invoice_line.price_subtotal,
                        'Price Subtotal(INR)': invoice_line.credit or (invoice_line.debit * sign),
                        'Price Total': invoice_line.price_total, 'Invoice Untaxed Amt': un_tax_amt,
                        'Invoice Tax Amount': invoice_line.move_id.amount_tax,
                        'voucher_shipping_address': invoice_line.move_id.partner_shipping_id.display_name or '',
                        # 'voucher_remark': invoice_line.move_id.header_narration or '',
                        # 'Narration': invoice_line.move_id.header_narration or (invoice_line.move_id.narration if isinstance(invoice_line.move_id.narration, str) else '') or '',
                        # 'Line Narration': invoice_line.narration or '',
                        'Ref No': (invoice_line.sale_line_ids.order_id[:1].client_order_ref or '') if invoice_line.sale_line_ids else '',
                        'Payment Term': invoice_line.move_id.invoice_payment_term_id.name or '',
                        # 'Warehouse': (invoice_line.sale_line_ids.order_id[:1].warehouse_id.name or '') if invoice_line.sale_line_ids else (
                        #     request.env['pos.order'].sudo().search([('account_move', '=', invoice_line.move_id.id)], limit=1).session_id.config_id.picking_type_id.warehouse_id.name or ''
                        # ),
                        'Invoice Total Amt': total_amt,
                        # 'Vehicle Number': invoice_line.move_id.vehicle_no or '',
                        'Eway Bill Number': getattr(invoice_line.move_id, 'l10n_in_ewaybill_name', ''),
                        'IRN Number': (invoice_line.move_id._get_l10n_in_edi_response_json().get('Irn') if hasattr(invoice_line.move_id, '_get_l10n_in_edi_response_json') else '') or getattr(invoice_line.move_id, 'l10n_in_irn_number', '') or ''}
                # Removed redundant bill-level tax columns
                data.update(DownloadReport.compute_taxes(invoice_line))

                # for line in invoices.line_ids:
                #     account_name = line.account_id.name
                #     if not account_name:
                #         continue
                #     if 'gst' in account_name.lower():
                #         if account_name not in gst_data:
                #             gst_data[account_name] = line.debit + line.credit
                #         else:
                #             gst_data[account_name] += line.debit + line.credit
                #     if account_name not in data:
                #         data[account_name] = line.debit + line.credit
                #     else:
                #         data[account_name] += line.debit + line.credit

                data_rows.append(data)
            DownloadReport.dataframe_operations(data_rows, sheet_name, writer)
            return data_rows, gst_data

        sales_data, gst_data = get_detailed_sales_data(invoice_data.filtered(lambda x: x.move_type == "out_invoice"),
                                                       'Sales Register')
        sales_return_data, gst_data1 = get_detailed_sales_data(invoice_data.filtered(lambda x: x.move_type == "out_refund"),
                                                                'Sales Return')
        consolidated_return_data = []
        for row in sales_return_data:
            new_row = row.copy()
            for key, val in new_row.items():
                if isinstance(val, (int, float)) and key not in ['Unit Price', 'Discount']:
                    new_row[key] = -abs(val)
            consolidated_return_data.append(new_row)
        consolidated_data = sales_data + consolidated_return_data
        DownloadReport.dataframe_operations(consolidated_data, 'Consolidated', writer)

        total_gst_op = sum(gst_data.values())

        workbook = writer.book
        title_format = DownloadReport.title_format(workbook)
        txt_font = DownloadReport.txt_font(workbook)
        txt_font2 = DownloadReport.txt_font2(workbook)

        summary_sheet.write('A1', 'Report: Detailed Sales and Detail Register Report', title_format)
        summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        summary_sheet.write('A3', f"GST CALCULATION FOR: {start_date} to {end_date}")
        summary_sheet.write('A5', f"GST OUTPUT", txt_font)
        summary_sheet.write('A16', f"GST OUTPUT TOTAL", txt_font)
        summary_sheet.write('B16', total_gst_op, txt_font)
        summary_sheet.write('A22', f"GST INPUT", txt_font)
        summary_sheet.write('A30', f" Less: - Set - off  c / f of GST for the month of July -2022", txt_font)
        summary_sheet.write('A37', f" Less:- Reverse Charge & Joint Charge Paid for the month of July-2022", txt_font)
        summary_sheet.write('A45', f" Total GST Payable", txt_font)
        summary_sheet.write('A47', f" Reverse charge and Joint charge Payable ", txt_font)
        summary_sheet.write('A52', f" Total Reverse charge and Joint charge Payable", txt_font)

        key_col = 7
        val_col = 7
        for key, value in gst_data.items():
            summary_sheet.write('A' + str(key_col), key, txt_font2)
            summary_sheet.write('B' + str(val_col), round(value), txt_font2)
            key_col += 1
            val_col += 1
        writer.close()
        out = fp.getvalue()
        pdfhttpheaders = [('Content-Type', 'application/octet-stream'),
                          ('Content-Disposition', content_disposition(f"Detail Sales and Return Register Report.xlsx"))]
        return request.make_response(out, headers=pdfhttpheaders)

    @staticmethod
    def sales_register(start_date, end_date, invoice_data, company_id, *args, **kwargs):
        fp = BytesIO()
        writer = pd.ExcelWriter(fp, engine='xlsxwriter')
        summary_sheet = DownloadReport.create_summary_sheet(writer)

        def get_sales_data(invoices, sheet_name):
            gst_data = {}
            data_rows = list()
            for invoice in invoices:
                partner_id = invoice.partner_id
                un_tax_amt = invoice.amount_untaxed
                total_amt = invoice.amount_total
                data = {'Journal': invoice.journal_id.name,
                        'Invoice NO': invoice.name,
                        'Invoice Date': invoice.invoice_date.strftime('%d-%m-%Y') if invoice.invoice_date else '',
                        'Salesperson': invoice.invoice_user_id.name,
                        'Sale Order': invoice.invoice_origin if invoice.invoice_origin else '',
                        'Sale Order Date': (invoice.invoice_line_ids.sale_line_ids.order_id[:1].date_order.strftime('%d-%m-%Y') if invoice.invoice_line_ids.sale_line_ids and invoice.invoice_line_ids.sale_line_ids.order_id[:1].date_order else '') if invoice.invoice_line_ids.sale_line_ids else '',
                        'Customer': partner_id.name if partner_id.name else partner_id.parent_id.name,
                        'Customer State': DownloadReport.get_partner_state(invoice, partner_id),
                        'GST NO': invoice.partner_id.vat, 'Currency': invoice.currency_id.name,
                        'Untaxed Amt': un_tax_amt, 'Tax Amount': invoice.amount_tax, 'Total Amt': total_amt,
                        # 'Header Narration': invoice.header_narration or (invoice.narration if isinstance(invoice.narration, str) else '') or '',
                        # 'Vehicle Number': invoice.vehicle_no or '',
                        'Eway Bill Number': getattr(invoice, 'l10n_in_ewaybill_name', ''),
                        'IRN Number': (invoice._get_l10n_in_edi_response_json().get('Irn') if hasattr(invoice, '_get_l10n_in_edi_response_json') else '') or getattr(invoice, 'l10n_in_irn_number', '') or ''}

                for line in invoice.line_ids:
                    account_name = line.account_id.name
                    if not account_name:
                        continue
                    if 'gst' in account_name.lower():
                        if account_name not in gst_data:
                            gst_data[account_name] = line.debit + line.credit
                        else:
                            gst_data[account_name] += line.debit + line.credit
                    if account_name not in data:
                        data[account_name] = line.debit + line.credit
                    else:
                        data[account_name] += line.debit + line.credit
                    if line.analytic_distribution:
                        analytic_account = request.env['account.analytic.account'].sudo().search(
                            [('id', '=', (list(line.analytic_distribution))[0])])
                        data['Analytic'] = analytic_account.name

                data_rows.append(data)
            DownloadReport.dataframe_operations(data_rows, sheet_name, writer)
            return data_rows, gst_data

        sales_data, gst_data = get_sales_data(invoice_data.filtered(lambda x: x.move_type == "out_invoice"), 'Sales Register')
        sales_return_data, gst_data1 = get_sales_data(invoice_data.filtered(lambda x: x.move_type == "out_refund"), 'Sales Return')
        consolidated_return_data = []
        for row in sales_return_data:
            new_row = row.copy()
            for key, val in new_row.items():
                if isinstance(val, (int, float)) and key not in ['Unit Price', 'Discount']:
                    new_row[key] = -abs(val)
            consolidated_return_data.append(new_row)
        consolidated_data = sales_data + consolidated_return_data
        DownloadReport.dataframe_operations(consolidated_data, 'Consolidated', writer)
        total_gst_op = sum(gst_data.values())

        workbook = writer.book
        title_format = DownloadReport.title_format(workbook)
        txt_font = DownloadReport.txt_font(workbook)
        txt_font2 = DownloadReport.txt_font2(workbook)
        txt_font3 = DownloadReport.txt_font3(workbook)

        summary_sheet.write('A1', 'Report: Sales and Return Register', title_format)
        # summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        # summary_sheet.write('A3', f"Sales and Return Register Report from: {start_date} to {end_date}")

        # summary_sheet.merge_range('A1:D1', 'Tigerpug 1st GSTIN', title_format)
        summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        summary_sheet.write('A3', f"GST CALCULATION FOR: {start_date} to {end_date}")
        summary_sheet.write('A5', f"GST OUTPUT", txt_font)
        summary_sheet.write('A16', f"GST OUTPUT TOTAL", txt_font)
        summary_sheet.write('B16', total_gst_op, txt_font)
        summary_sheet.write('A22', f"GST INPUT", txt_font)
        summary_sheet.write('A30', f" Less: - Set - off  c / f of GST for the month of July -2022", txt_font)
        summary_sheet.write('A37', f" Less:- Reverse Charge & Joint Charge Paid for the month of July-2022", txt_font)
        summary_sheet.write('A45', f" Total GST Payable", txt_font)
        summary_sheet.write('A47', f" Reverse charge and Joint charge Payable ", txt_font)
        summary_sheet.write('A52', f" Total Reverse charge and Joint charge Payable", txt_font)

        key_col = 7
        val_col = 7
        for key, value in gst_data.items():
            summary_sheet.write('A' + str(key_col), key, txt_font2)
            summary_sheet.write('B' + str(val_col), value, txt_font2)
            key_col += 1
            val_col += 1

        writer.close()
        out = fp.getvalue()
        pdfhttpheaders = [('Content-Type', 'application/octet-stream'),
                          ('Content-Disposition', content_disposition(f"Sales and Return Register Report.xlsx"))]
        return request.make_response(out, headers=pdfhttpheaders)

    @http.route('/download/reports', type='http', auth='user', methods=['GET'], csrf=False)
    def portal_my_quotes(self, **kwargs):
        report_for, start_date, end_date, company_id, move_type, journal_id = request.params.get('report_for'), \
            request.params.get('start_date'), \
            request.params.get('end_date'), \
            request.params.get('company_id'), \
            request.params.get('move_type'), \
            request.params.get('journal_id')
        domain = [('state', '=', 'posted'), ('date', '>=', start_date),
                  ('date', '<=', end_date)]
        if move_type == "sales":
            domain.append(('move_type', 'in', ['out_invoice', 'out_refund']))
        else:
            domain.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        if journal_id != "False":
            domain.append(('journal_id', 'in', ast.literal_eval(journal_id)))
        invoices = request.env['account.move'].search(domain)

        if not invoices:
            return self.no_data_found()
        return getattr(self, report_for)(start_date, end_date, invoices, company_id)

    # Purchase Register
    @staticmethod
    def detail_purchase_register(start_date, end_date, invoice_data, company_id, *args, **kwargs):
        fp = BytesIO()
        writer = pd.ExcelWriter(fp, engine='xlsxwriter')
        summary_sheet = DownloadReport.create_summary_sheet(writer)

        def get_detail_bills_data(invoices, sheet_name):
            data_rows = list()
            gst_data = {}
            for invoice_line in invoices.invoice_line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_note')):
                sign = -1 if invoice_line.move_id.move_type == 'out_invoice' else 1
                # added by vatsal
                amt_tax = 0.0
                for line in invoice_line.move_id.line_ids:
                    if line.tax_line_id:
                        tax_group = line.tax_line_id.tax_group_id
                        tax_group_name = tax_group.name if tax_group else ''
                        if tax_group_name not in ["TDS", "TCS"]:
                            amt_tax += abs(line.amount_currency)
                # custom code ends
                un_tax_amt = invoice_line.move_id.amount_untaxed
                total_amt = invoice_line.move_id.amount_total
                final_total = (un_tax_amt or 0.0) + amt_tax
                tax_tot = amt_tax

                data = {'Bill NO': invoice_line.move_id.name, "Bill Reference": invoice_line.move_id.ref,
                        'Accounting Date': invoice_line.move_id.date.strftime('%d-%m-%Y') if invoice_line.move_id.date else '',
                        "Bill Date": invoice_line.move_id.invoice_date.strftime('%d-%m-%Y') if invoice_line.move_id.invoice_date else '',
                        'Purchase Representative': invoice_line.move_id.invoice_user_id.name,
                        'Parent Company': invoice_line.company_id.parent_id.name if invoice_line.company_id.parent_id.name else '-',
                        'Company': invoice_line.company_id.name,
                        'Vendor': invoice_line.move_id.partner_id.name,
                        'Vendor State': DownloadReport.get_partner_state(invoice_line.move_id, invoice_line.move_id.partner_id),
                        'Contact Tags': ', '.join(invoice_line.move_id.partner_id.category_id.mapped('name')) if invoice_line.move_id.partner_id.category_id else '',
                        'GST NO': invoice_line.partner_id.vat,
                        'PAN': invoice_line.partner_id.l10n_in_pan_entity_id.name,
                        'Product': invoice_line.product_id.name,
                        'Product Tags': ', '.join(invoice_line.product_id.product_tag_ids.mapped('name')) if invoice_line.product_id.product_tag_ids else '',
                        'HSN Code': getattr(invoice_line, 'l10n_in_hsn_code', False) or getattr(invoice_line, 'hsn_code', False) or (invoice_line.product_id and (getattr(invoice_line.product_id, 'l10n_in_hsn_code', False) or getattr(invoice_line.product_id, 'hsn_code', False))) or '',
                        'category': invoice_line.product_id.categ_id.name,

                        'Quantity': invoice_line.quantity,

                        'UOM': invoice_line.product_uom_id.name,
                        'Currency': invoice_line.currency_id.name,
                        'Unit Price': invoice_line.price_unit,
                        # 'Currency': invoice_line.move_id.currency_id.name,
                        'Discount': invoice_line.discount,
                        'Price Subtotal(In Currency)': invoice_line.price_subtotal,
                        'Price Subtotal(INR)': invoice_line.credit or (invoice_line.debit * sign),
                        # 'Price Total': invoice_line.price_total, commented on purpose
                        'Bill Untaxed Amt': un_tax_amt,
                        'Bill Tax Amount': tax_tot,
                        'Bill Total Amt': final_total}

                if invoice_line.analytic_distribution:
                    analytic_account = request.env['account.analytic.account'].sudo().search(
                        [('id', '=', (list(invoice_line.analytic_distribution))[0])])
                    data['Analytic'] = analytic_account.name
                    # 'Bill Tax Amount': invoice_line.move_id.amount_tax, 'Bill Total Amt': total_amt}
                # Removed redundant bill-level tax columns
                data.update(DownloadReport.compute_taxes(invoice_line))

                # for line in invoices.line_ids:
                #     account_name = line.account_id.name
                #     if not account_name:
                #         continue
                #     if 'gst' in account_name.lower():
                #         if account_name not in gst_data:
                #             gst_data[account_name] = line.debit + line.credit
                #         else:
                #             gst_data[account_name] += line.debit + line.credit
                #     if account_name not in data:
                #         data[account_name] = line.debit + line.credit
                #     else:
                #         data[account_name] += line.debit + line.credit
                data_rows.append(data)
            DownloadReport.dataframe_operations(data_rows, sheet_name, writer)
            return data_rows, gst_data

        purchase_data, gst_data = get_detail_bills_data(invoice_data.filtered(lambda x: x.move_type == 'in_invoice'),
                                                        'Purchase Register')
        purchase_return_data, gst_data1 = get_detail_bills_data(invoice_data.filtered(lambda x: x.move_type == 'in_refund'),
                                                                'Purchase Return')
        consolidated_return_data = []
        for row in purchase_return_data:
            new_row = row.copy()
            for key, val in new_row.items():
                if isinstance(val, (int, float)) and key not in ['Unit Price', 'Discount']:
                    new_row[key] = -abs(val)
            consolidated_return_data.append(new_row)
        consolidated_data = purchase_data + consolidated_return_data
        DownloadReport.dataframe_operations(consolidated_data, 'Consolidated', writer)

        total_gst_op = sum(gst_data.values())
        workbook = writer.book
        title_format = DownloadReport.title_format(workbook)
        txt_font = DownloadReport.txt_font(workbook)
        txt_font2 = DownloadReport.txt_font2(workbook)
        txt_font3 = DownloadReport.txt_font3(workbook)

        summary_sheet.write('A1', 'Report: Detailed Purchase and Return Register', title_format)
        # summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        # summary_sheet.write('A3', f"Detailed Purchase and Return Register Report from: {start_date} to {end_date}")
        # summary_sheet.merge_range('A1:D1', 'Tigerpug 1st GSTIN', title_format)
        summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        summary_sheet.write('A3', f"GST CALCULATION FOR: {start_date} to {end_date}")
        summary_sheet.write('A5', f"GST OUTPUT", txt_font)
        summary_sheet.write('A18', f"GST OUTPUT TOTAL", txt_font)
        summary_sheet.write('B18', total_gst_op, txt_font)
        summary_sheet.write('A22', f"GST INPUT", txt_font)
        summary_sheet.write('A30', f" Less: - Set - off  c / f of GST for the month of July -2022", txt_font)
        summary_sheet.write('A37', f" Less:- Reverse Charge & Joint Charge Paid for the month of July-2022", txt_font)
        summary_sheet.write('A45', f" Total GST Payable", txt_font)
        summary_sheet.write('A47', f" Reverse charge and Joint charge Payable ", txt_font)
        summary_sheet.write('A52', f" Total Reverse charge and Joint charge Payable", txt_font)

        key_col = 7
        val_col = 7

        for key, value in gst_data.items():
            summary_sheet.write('A' + str(key_col), key, txt_font2)
            summary_sheet.write('B' + str(val_col), value, txt_font2)
            key_col += 1
            val_col += 1
        writer.close()
        out = fp.getvalue()
        pdfhttpheaders = [('Content-Type', 'application/octet-stream'),
                          ('Content-Disposition', content_disposition(f"Detail Purchase Register Report.xlsx"))]
        return request.make_response(out, headers=pdfhttpheaders)

    @staticmethod
    def purchase_register(start_date, end_date, invoice_data, company_id, *args, **kwargs):
        fp = BytesIO()
        writer = pd.ExcelWriter(fp, engine='xlsxwriter')
        summary_sheet = DownloadReport.create_summary_sheet(writer)

        # def get_bills_data(invoices, sheet_name):
        #     data_rows = list()
        #     gst_data = {}
        #     for invoice in invoices:
        #         taxes = invoice.tax_totals
        #         print(taxes)
        #         # sign = -1 if invoice.move_id.move_type == 'out_invoice' else 1
        #         # added by vatsal
        #         amt_tax = 0.0
        #         pairs = [(key, value)
        #                  for key, values in taxes['groups_by_subtotal'].items()
        #                  for value in values]
        #         for pair in pairs:
        #             for d in pair:
        #                 if "tax_group_name" in d:
        #                     if d['tax_group_name'] not in ["TDS", "TCS"]:
        #                         amt_tax += d['tax_group_amount']
        def get_bills_data(invoices, sheet_name):
            data_rows = list()
            gst_data = {}
            for invoice in invoices:
                # added by vatsal
                amt_tax = 0.0
                for line in invoice.line_ids:
                    if line.tax_line_id:
                        tax_group = line.tax_line_id.tax_group_id
                        tax_group_name = tax_group.name if tax_group else ''
                        if tax_group_name not in ["TDS", "TCS"]:
                            amt_tax += abs(line.amount_currency)
                # custom code ends
                un_tax_amt = invoice.amount_untaxed
                total_amt = invoice.amount_total
                final_total = (un_tax_amt or 0.0) + amt_tax
                tax_tot = amt_tax
                data = {'Bill NO': invoice.name, "Bill Reference": invoice.ref,
                        'Accounting Date': invoice.date.strftime('%d-%m-%Y') if invoice.date else '',
                        'Bill Date': invoice.invoice_date.strftime('%d-%m-%Y') if invoice.invoice_date else '',
                        'Purchase Representative': invoice.invoice_user_id.name,
                        'Vendor': invoice.partner_id.name,
                        'Vendor State': DownloadReport.get_partner_state(invoice, invoice.partner_id),
                        'GST NO': invoice.partner_id.vat,
                        # 'Price Subtotal(In Currency)': invoice.amount_total,
                        # 'Price Subtotal(INR)': invo   ice.credit or (invoice.debit * sign),
                        'Currency': invoice.currency_id.name, 'Untaxed Amt': un_tax_amt, 'Tax Amount': tax_tot,
                        'Total Amt': final_total}
                # 'Tax Amount(W/o Tds)': invoice.amount_tax, commented on purpose
                # 'Total Amt(W/o Tds)': total_amt            commented on purpose
                for line in invoice.line_ids:
                    account_name = line.account_id.name
                    if not account_name:
                        continue
                    if 'gst' in account_name.lower():
                        if account_name not in gst_data:
                            gst_data[account_name] = line.debit + line.credit
                        else:
                            gst_data[account_name] += line.debit + line.credit
                    if account_name not in data:
                        data[account_name] = line.debit + line.credit
                    else:
                        data[account_name] += line.debit + line.credit

                    if line.analytic_distribution:
                        analytic_account = request.env['account.analytic.account'].sudo().search(
                            [('id', '=', (list(line.analytic_distribution))[0])])
                        data['Analytic'] = analytic_account.name
                data_rows.append(data)
            DownloadReport.dataframe_operations(data_rows, sheet_name, writer)
            return data_rows, gst_data

        purchase_data, gst_data = get_bills_data(invoice_data.filtered(lambda x: x.move_type == 'in_invoice'), 'Purchase Register')
        purchase_return_data, gst_data1 = get_bills_data(invoice_data.filtered(lambda x: x.move_type == 'in_refund'), 'Purchase Returns')
        consolidated_return_data = []
        for row in purchase_return_data:
            new_row = row.copy()
            for key, val in new_row.items():
                if isinstance(val, (int, float)) and key not in ['Unit Price', 'Discount']:
                    new_row[key] = -abs(val)
            consolidated_return_data.append(new_row)
        consolidated_data = purchase_data + consolidated_return_data
        DownloadReport.dataframe_operations(consolidated_data, 'Consolidated', writer)

        total_gst_op = sum(gst_data.values())
        workbook = writer.book
        title_format = DownloadReport.title_format(workbook)
        txt_font = DownloadReport.txt_font(workbook)
        txt_font2 = DownloadReport.txt_font2(workbook)
        txt_font3 = DownloadReport.txt_font3(workbook)
        summary_sheet.write('A1', 'Report: Purchase Register', title_format)
        # summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        # summary_sheet.write('A3', f"Purchase Register Report from: {start_date} to {end_date}")
        # summary_sheet.merge_range('A1:D1', 'Tigerpug 1st GSTIN', title_format)
        summary_sheet.write('A2', f"Company Name: {DownloadReport.get_company_details(company_id)}")
        summary_sheet.write('A3', f"GST CALCULATION FOR: {start_date} to {end_date}")
        summary_sheet.write('A5', f"GST OUTPUT", txt_font)
        summary_sheet.write('A18', f"GST OUTPUT TOTAL", txt_font)
        summary_sheet.write('B18', total_gst_op, txt_font)
        summary_sheet.write('A22', f"GST INPUT", txt_font)
        summary_sheet.write('A30', f" Less: - Set - off  c / f of GST for the month of July -2022", txt_font)
        summary_sheet.write('A37', f" Less:- Reverse Charge & Joint Charge Paid for the month of July-2022", txt_font)
        summary_sheet.write('A45', f" Total GST Payable", txt_font)
        summary_sheet.write('A47', f" Reverse charge and Joint charge Payable ", txt_font)
        summary_sheet.write('A52', f" Total Reverse charge and Joint charge Payable", txt_font)

        key_col = 7
        val_col = 7
        for key, value in gst_data.items():
            summary_sheet.write('A' + str(key_col), key, txt_font2)
            summary_sheet.write('B' + str(val_col), value, txt_font2)
            key_col += 1
            val_col += 1

        writer.close()
        out = fp.getvalue()
        pdfhttpheaders = [('Content-Type', 'application/octet-stream'),
                          ('Content-Disposition', content_disposition(f"Purchase Register Report.xlsx"))]
        return request.make_response(out, headers=pdfhttpheaders)
