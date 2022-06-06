# -*- coding: utf-8 -*-
{
    'name': "Odoo PSA",
    'author': "E3k Solutions",
    'website': "https://www.e3k.ca/",
    'category': 'Uncategorized',
    'summary': """Timesheet - Version 13""",
    'License': 'LGPL Version 3',
    'version': '15.1.0.1',
    'depends': [
        'sale_management',
        'sale_expense',
        'hr',
        'hr_timesheet',
        'sale_timesheet',
        'sales_team',
        'timesheet_grid',
        'hr_expense',
        'account',
        'analytic',
        'sale_timesheet_enterprise'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/timesheet_security.xml',
        'views/account_move.xml',
        'views/hr_expense.xml',
        'views/sale_order_views.xml',
        'views/product_view.xml',
        'views/res_users.xml',
        'views/res_partner.xml',
        'views/hr_timesheet.xml',
        'views/project_task.xml',
        'views/project.xml',
        'views/tarification.xml',
        'wizard/project_create_sale_order.xml',
        'wizard/sale_make_invoice_advance_views.xml',
        'reports/socanin_template.xml',
        'reports/standard_template.xml',
        'reports/report_invoice.xml',
        'menus/menus.xml'
    ],
    'assets': {
        'web.assets_backend': ["/e3k_psa/static/src/js/list_controller.js"]
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
