{
    "name": "Soles - Gestión de Tesorería",
    "version": "18.0.1.2.0",
    "summary": "Solicitudes de pago, programación, recurrencias y control de Tesorería",
    "description": """
Gestión de Tesorería para Soles.

Incluye:
- Solicitudes de pago.
- Vinculación opcional con Aprobaciones.
- Solicitudes extraordinarias.
- Factura PDF/XML y documentos anexos.
- Programación y calendario de pagos.
- Alertas mediante actividades de Odoo.
- Pagos recurrentes.
- Equipos y responsables de Tesorería.
- Configuración de tipos de aprobación habilitados.
    """,
    "author": "Soles",
    "category": "Accounting/Treasury",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "approvals",
    ],
    "data": [
        "security/treasury_security.xml",
        "security/ir.model.access.csv",
        "data/treasury_data.xml",
        "data/mail_template.xml",
        "views/treasury_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
}
