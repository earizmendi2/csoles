# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Fixed Header List View',
    'version': '15.0',
    'sequence': 1,
    'summary': """
        Sticky Tree View Fixed Tree View, All in one Tree View, Fix List Header Table, Fixed Table Header 
    """,
    'description': "Fixed Header List View is very useful for displaying list headers within Odoo.",
    'author': 'NEWAY Solutions',
    'maintainer': 'NEWAY Solutions',
    'price': '0.0',
    'currency': 'USD',
    'website': 'https://neway-solutions.com',
    'license': 'LGPL-3',
    'images': [
        'static/description/screenshot.gif'    
    ],
    'depends': [
        'web'
    ],
    'data': [
        
    ],
    'assets': {
        'web.assets_backend': [
            'fixed_header_list/static/src/scss/list.scss',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
