# -*- coding: utf-8 -*-
{
    'name': 'EDI Payment truncated 2 digits',
    'version': '1.2',
    'images':['static/description/icon.png'],
    'summary': 'REP TRUNCADO A 2 DIGITOS',
    'description': "Toma los valores de los pagos y los trunca a 2 digitos para poderlos timbrar",
    'category': 'Generic Modules',
    'author': 'Ivan Legarda',
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