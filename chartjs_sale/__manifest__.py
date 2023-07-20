# -*- coding: utf-8 -*-
{
    'name': "Dashboard Rabbit",
    "summary": "The dashboard includes a revenue chart, a profit chart, an order count chart, a product-wise revenue chart",
    'description': """The dashboard includes a revenue chart, a profit chart, an order count chart, a product-wise revenue chart, an employee-wise revenue chart, total revenue, cash revenue, bank transfer revenue, purchasing expenses, and visually complete customer statistics.
    """,
    "price": "0",
    "currency": "EUR",
    'license': 'GPL-3',
    'author': "TTN SOFTWARE",
    'website': "TTNSOFTWARE.STORE",
    'category': 'App',
    'version': '15.2.2',
    'depends': ['base', 'mrp', 'sale', 'pos_sale', "hr", "purchase"],

    'data': [
        'security/ir.model.access.csv',
        'views/owl_templates/owl_customer.xml',
        'views/views.xml',
        'views/templates.xml',


    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'chartjs_sale/static/src/xml/*',
            'chartjs_sale/static/src/xml/owl/*',
        ],
        'web.assets_backend': [
            'chartjs_sale/static/src/components/**/*',
            'chartjs_sale/static/src/scss/**/*',
            'chartjs_sale/static/lib/*',
            'chartjs_sale/static/src/js/**/*',
            'chartjs_sale/static/src/js/*',
        ],

    },

    'images': ['static/img/main_screenshot.gif']
}
