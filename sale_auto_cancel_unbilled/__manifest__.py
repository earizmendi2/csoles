{
    'name': 'Ventas - Cancelación automática de órdenes sin facturar',
    'version': '18.0.1.0.0',
    'summary': (
        'Cancela automáticamente órdenes de venta confirmadas que llevan '
        'más de X días sin generar ninguna factura.'
    ),
    'description': """
Cancelación automática de órdenes de venta sin facturar
=========================================================

Agrega una tarea programada (cron) que cancela automáticamente las órdenes
de venta confirmadas (state = 'sale') que aún no tienen ninguna factura
asociada (invoice_status = 'no', "Nada que facturar") y llevan más de X
días desde su creación.

* La cancelación usa el flujo estándar de Odoo (action_cancel()), sin
  modificar el estado directamente ni pisar validaciones del core.
* Cada orden cancelada recibe una nota en su chatter explicando el motivo,
  para trazabilidad del equipo de ventas.
* El número de días (X) es configurable en Ventas > Configuración > Ajustes,
  o directamente en el parámetro del sistema 'sale_auto_cancel.days'. Un
  valor de 0 desactiva la cancelación automática (valor por defecto).
* No toca cotizaciones sin confirmar, ni órdenes con facturación parcial o
  total (invoice_status en 'to invoice' o 'invoiced').
""",
    'category': 'Sales/Sales',
    'author': 'Rubén Castillo',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
