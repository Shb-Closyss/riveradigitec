{
    'name': 'RIVERA DIGITEC ODOO',
    'version': '19.0.1.0.0',
    'category': 'Operations',
    'summary': 'ERP Customizations for RIVERA DIGITEC (I) PVT. LTD.',
    'description': """
RIVERA DIGITEC (I) PVT. LTD.
============================

Custom Odoo 19 ERP implementation covering:

- Sales
- Purchase
- Inventory
- Accounting

This module will contain company-specific ERP customizations,
business processes, workflows, reports, and enhancements.
    """,

    'author': 'Closyss Technologies LLP',
    'website': False,

    'license': 'LGPL-3',

    'depends': [
        'sale_management',
        'purchase',
        'stock',
        'account',
        'sale_stock',
        'purchase_stock',
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'views/product_brand_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_warehouse_views.xml',
    ],

    'assets': {},

    'installable': True,
    'application': True,
    'auto_install': False,
}