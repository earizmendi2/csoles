# -*- coding: utf-8 -*-
{
    'name': 'Upload files to cloud',
    'version': '1.0',
    'images':['static/description/icon.png'],
    'summary': """It allows you to upload database files to Google Cloud to free up occupied space; it requires your JSON configuration and bucket ready before uploading.""",
    'description': "",
    'category': 'Document Managment',
    'author': 'Ivan Legarda',
    "depends"              :  ['base','web'],
    'data': [],
    
    # 'demo': ['data/demo.xml'],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
    "price"                :  250,
    "currency"             :  "USD",
    "pre_init_hook"        :  "pre_init_check",  
    "external_dependencies":  {'python': ['google-cloud-storage']},
}

