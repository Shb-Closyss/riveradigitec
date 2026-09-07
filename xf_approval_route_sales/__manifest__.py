# -*- coding: utf-8 -*-
{
    'name': 'Sales Approval',
    'version': '1.1.1',
    'summary': """""",
    'category': '',
    'author': 'Closyss Technologies',
    'support': 'info@closyss.com',
    'website': 'https://www.closyss.com',
    'license': 'OPL-1',
    'description': """
    """,
    'data': [
        'views/res_config_settings.xml',
        'views/sales_order.xml',
        # 'views/expense_approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base','sale',
        'purchase'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
