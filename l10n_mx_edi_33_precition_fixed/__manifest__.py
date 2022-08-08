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
                'account_edi',
                'l10n_mx',                
    ],
    'data': [
        'data/cfdi_33.xml',
    ],
    
    # 'demo': ['data/demo.xml'],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
}

