# -*- coding: utf-8 -*-
{
    'name': 'CFDI Decimal Presition Fixed v3.3',
    'version': '1.0',
    'images':['static/description/icon.png'],
    'summary': """CFDI Decimal Presition Fixed v3.3""",
    'description': "",
    'category': 'Generic Modules',
    'author': 'McLennan Foster',
    'depends': [
                'base',
                'account',
                'l10n_mx_edi'
    ],
    'data': [
        'data/cfdi_33.xml',
    ],
    
    # 'demo': ['data/demo.xml'],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
}

