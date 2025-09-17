# -*- coding: utf-8 -*-
{
    'name': "Smart! Product Suggester",
    'version': '1.0',
    'summary': "This module allows you to suggest products to your customers on their purchase behaviour.",
    'author': 'ErpMstar Solutions',
    'category': 'Management System',
    'sequence': 8,

    'website': '',

    'depends': ['sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_suggested_product.xml',
        'data/cron_update_knowledge_base.xml',
        'wizard/add_suggested_product_view.xml',
    ],
    'images': [
        'static/description/sugg_add.jpg',
    ],
    'installable': True,
    'auto_install': False,
    'price': 50,
    'currency': 'EUR',
    'bootstrap': True,
    'application': True,
    'external_dependencies': {
        'python': ['efficient-apriori', 'dataclasses'],
    }
}
