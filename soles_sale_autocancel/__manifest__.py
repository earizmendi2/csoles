# -*- coding: utf-8 -*-
{
    'name': 'Cancelación Automática de Pedidos',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Cancela automáticamente pedidos confirmados sin facturar tras N días',
    'description': """
Cancelación Automática de Pedidos
==================================

Reemplaza la Acción Programada manual por un módulo configurable:

* Umbral de días, fecha de corte y canal de notificación editables desde Ajustes.
* Exclusión de cancelación automática por cliente o por pedido (checkbox), sin
  tocar código.
* Modo simulación para probar cambios de reglas sin cancelar nada real.
* Bitácora auditable de cada cancelación automática.
""",
    'author': 'Corporativo Soles',
    'depends': ['sale', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/autocancel_config_data.xml',
        'data/ir_cron.xml',
        'views/autocancel_config_views.xml',
        'views/autocancel_log_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
