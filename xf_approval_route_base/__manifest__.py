# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Approval Workflows [Base]',
    'version': '1.1.5',
    'summary': """
    """,
    'category': 'Purchases,Sales,Accounting,Document Management,Productivity',
    'author': 'Closyss Technologies',
    'support': 'info@closyss.com',
    'website': 'https://closyss.com/',
    'license': 'OPL-1',
    'description':
        """
        """,
    'data': [
        # Access
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        # UI
        'views/menu.xml',
        'views/approval_route.xml',
        'views/approval_role.xml',
        'views/approval_route_document.xml',
        'views/my_approvals.xml',
        'views/res_config_settings_views.xml',
        'wizard/reject_reason.xml'
    ],
    'demo': [
        'data/demo/approval_roles.xml',  # Remove that line, if you do not need demo data
    ],
    'depends': [
        'base_setup',
        'product',
        'analytic','hr',
          # Remove that dependency, if you do not need demo data
    ],
    'images': [
        'static/description/dynamic_approval_workflows.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
