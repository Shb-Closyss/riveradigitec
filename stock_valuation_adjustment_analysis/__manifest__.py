# -*- coding: utf-8 -*-
{
        'name': 'Stock Valuation Adjustment Analysis',
    'version': '19.0.1.0.0',
    'summary': 'Analyze stock valuation adjustments across all landed costs',
    'description': """
This module provides a read-only reporting screen/analysis dashboard for stock valuation adjustments across all landed costs in one report.
    """,
    'author': 'Closyss Technologies',
    'website': 'https://closyss.odoo.com/',
    'category': 'Inventory/Reporting',
    'depends': ['stock_landed_costs'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_valuation_adjustment_layer_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
