{
    'name': 'Perfiles de Acceso Dinámico',
    'version': '18.0.2.0.0',
    'summary': 'Gestiona acceso dinámico a campos y acciones basado en perfiles de usuario',
    'category': 'Technical',
    'description': """
        Este módulo permite la gestión de perfiles de usuario dinámicos que controlan el acceso a campos, botones, 
        menús, acciones y otras funcionalidades en los modelos de Odoo. Cada usuario puede tener múltiples perfiles,
        y cada perfil define qué campos o funcionalidades son visibles, requeridos, solo lectura o invisibles.
    """,
    'author': 'Martin López Guzmán',
    'website': "https://www.linkedin.com/in/martin-lopez3/",
    'depends': ['base', 'web'],
    'data': [
        'security/res_profile_security.xml',
        'security/ir.model.access.csv',
        'views/res_profile_views.xml',
        'views/res_users_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dynamic_access_profiles/static/src/js/field_rule_control.js',
            'dynamic_access_profiles/static/src/js/profile_org_chart.js',
            'dynamic_access_profiles/static/src/xml/profile_org_chart.xml',
            'dynamic_access_profiles/static/src/scss/profile_dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
        'auto_install': False,
        'license': 'OPL-1',
}
