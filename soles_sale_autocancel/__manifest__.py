# -*- coding: utf-8 -*-
{
    'name': 'Soles - Cancelación Automática de Pedidos',
    'version': '18.0.1.2.0',
    'category': 'Sales/Sales',
    'summary': 'Cancela automáticamente pedidos confirmados sin facturar tras N días',
    'description': """
Cancelación Automática de Pedidos
==================================

Módulo único que reemplaza la Acción Programada manual original y unifica
los dos prototipos previos (soles_sale_autocancel + sale_auto_cancel_unbilled):

* Umbral de días, fecha de corte y reglas editables desde una pantalla de
  configuración, sin tocar código.
* Detección de "sin facturar" vía invoice_ids vacío (ninguna factura
  generada), igual que el proceso original.
* Exclusión de cancelación automática por cliente o por pedido (checkbox),
  y un apartado dedicado en la configuración para gestionar todos los
  clientes excluidos desde un solo lugar (v1.2).
* Nota automática en el chatter de cada pedido cancelado, para trazabilidad.
* Notificaciones dirigidas: a un canal de Discuss, a usuarios específicos,
  y/o a grupos de seguridad completos (se resuelven dinámicamente al
  momento de notificar).
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
