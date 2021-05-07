# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

{
    'name': "Restrict Sales Order for Out of Stock Items",
    'currency': 'EUR',
    'price': 19.0,
    'images': ['static/description/img.jpg'],
    'live_test_url': 'https://youtu.be/nEA-ljLCQ6c',
    'license': 'Other proprietary',
    'summary': """Restrict sales users to confirm sales order for product out of stock.""",
    'description': """
This module allows you to shows you a list of low product stock details when confirming a sales order.
Restrict out of Stock Sales Order
restrict order
restrict sales order
restrict sale order
out of stock
product out of stock
    """,
    'author': "Probuse Consulting Service Pvt. Ltd.",
    'website': "http://www.probuse.com",
    'support': 'contact@probuse.com',
    'version': '1.1.2',
    'category' : 'Sales/Sales',
    'depends': [
        'sale_stock'
    ],
    'data':[
        'views/product_template_view.xml',
        'views/sale_order_view.xml',
        'wizard/saleorder_product_onhand_qty_view.xml'
    ],
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
