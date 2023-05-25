# -*- coding: utf-8 -*-
{
    'name': "Inventory Value,Sales ,Purchase Analysis Pivot Table For Odoo Community",

    'summary': """
    Sales Forecast by Product/
        Inventory/Purchase/Sales Analysis Pivot Tables""",

    'description': """
        Product Expected Sales , in comparison with the same period last year
        Inventory Analysis 
        Sales Analysis based on Sale Order Lines
        Purchase Analysis based on Purchase Order Lines
    """,

    'author': "Odoo Station",

    'website': "https://t.me/odoo_station/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Extra Tools',#Sales
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views_sale.xml',
        'views/views_purch.xml',
        'views/views_stock.xml',
        'views/views_product.xml',

    ],

    'images': ['images/main_screenshot.png'],

}
