# -*- coding: utf-8 -*-
{
    'name': 'CFDI Decimal Presition Fixed',
    'version': '1.0',
    'images':['static/description/icon.png'],
    'summary': """CFDI Decimal Presition Fixed""",
    'description': "",
    'category': 'Generic Modules',
    'author': 'McLennan Foster',
    'depends': [
                'base',
                'account',
                'l10n_mx_edi_40'
    ],
    'data': [
        'data/cfdi_40.xml',
    ],
    
    # 'demo': ['data/demo.xml'],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
}

