# -*- coding: utf-8 -*-
{
    'name': 'EDI Payment truncated 2 digits',
    'version': '1.0',
    'images':['static/description/icon.png'],
    'summary': 'REP TRUNCADO A 2 DIGITOS',
    'description': "",
    'category': 'Generic Modules',
    'author': 'McLennan Foster',
    'depends': [
                'base',                
                'account_edi',
                'l10n_mx',                
    ],
    'data': [
        'data/payment10.xml',
    ],        
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
}