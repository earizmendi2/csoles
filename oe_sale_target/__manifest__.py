{
    'name': 'Sale Target',
    'version': '15.0.0.1.0.0',
    'summary': 'To target the salesperson with the amount target',
    'description': 'To target the salesperson with the amount target',
    'category': 'Sale',
    'price': "8.68",
    'currency': "USD",
    'author': 'OE Dev',
    'website': 'https://oe-dev.odoo.com/',
    'license': 'OPL-1',
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
        'static/img/step1.PNG',
        'static/img/step2.PNG',
        'static/img/step3.PNG',
        'static/img/step4.PNG'
    ],
    'depends': ['sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/group_data.xml',
        'data/ir_sequence_data.xml',
        'views/view_sale_target.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'external_dependencies': {
        'python': [],
    }
}