{
    'name': 'Legacy Financial Reports',
    'version': '17.0.1.2.0',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'depends': ['account_reports', 'stock', 'stock_account', 'mrp', 'legacy_mrp_master_data'],
    'data': ['data/reports.xml', 'data/budgets.xml', 'views/configuration.xml', 'views/pdf.xml'],
    'assets': {'web.assets_backend': [
        'legacy_financial_reports/static/src/report.scss',
        'legacy_financial_reports/static/src/warnings.xml',
    ]},
    'installable': True,
    'application': False,
}
