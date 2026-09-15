# -*- coding: utf-8 -*-
{
    'name': 'Constancia SAT',
    'version': '18.0.1.4.9',
    'summary': 'Crea y actualiza contactos desde la Constancia de Situación Fiscal del SAT',
    'description': """
Permite crear y actualizar contactos de Odoo a partir de la Constancia de
Situación Fiscal del SAT en formato PDF.

Extrae información fiscal como RFC, nombre o razón social, régimen fiscal,
código postal fiscal, domicilio fiscal y URL oficial de verificación del SAT.
    """,
    'author': 'Cusoft',
    'website': 'https://www.cusoft.mx',
    'support': 'apps@cusoft.mx',
    'live_test_url': 'http://portal.odoo.lat/probar-odoo/live-test/4d7E9jZxP0pdbE8XIZCKvmL6zHyOtZXX',
    'category': 'Contacts',
    'license': 'LGPL-3',
    'depends': [
        'contacts',
    ],
    'external_dependencies': {
        'python': [
            'PyPDF2',
            'PyMuPDF',
            'pyzbar',
            'Pillow',
            'beautifulsoup4',
            'requests',
            'certifi',
            'truststore',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/main_screenshot.png',
        'static/description/icon.png',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/cs_partner_tax_certificate_import_wizard_views.xml',
        'views/cs_partner_tax_certificate_update_wizard_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
}
