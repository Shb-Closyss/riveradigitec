# -*- coding: utf-8 -*-
{
    'name': 'Boss Purchase Approval',
    # 'version': '1.1.1',
    'summary': """""",
    'category': '',
    'author': 'Closyss Technologies',
    'support': 'info@closyss.com',
    'website': 'https://www.closyss.com',
    'license': 'OPL-1',
    'description': """
    """,
    'data': [
        'views/purchase.xml',
        'views/res_config_settings.xml',
    ],
    'depends': [
        'xf_approval_route_base','purchase'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
