from datetime import timedelta

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cron_auto_cancel_unbilled_orders(self):
        """Cancela órdenes de venta confirmadas que llevan más de X días sin
        generar ninguna factura.

        Usa el flujo estándar de cancelación de Odoo (action_cancel()) en
        vez de escribir el estado directamente, para respetar cualquier
        validación o lógica adicional que el core (u otros módulos)
        agreguen a ese método.

        X se toma del parámetro del sistema 'sale_auto_cancel.days'
        (configurable en Ventas > Configuración > Ajustes). Si es 0 o no
        está definido, el cron no hace nada.
        """
        days = int(self.env['ir.config_parameter'].sudo().get_param('sale_auto_cancel.days', 0) or 0)
        if not days:
            return

        cutoff = fields.Datetime.now() - timedelta(days=days)
        orders = self.search([
            ('state', '=', 'sale'),
            ('invoice_status', '=', 'no'),
            ('create_date', '<=', cutoff),
        ])

        for order in orders:
            order.message_post(
                body=_(
                    "Cancelada automáticamente: lleva más de %(days)s días confirmada "
                    "sin generar ninguna factura (Nada que facturar).",
                    days=days,
                )
            )
            try:
                order.action_cancel()
            except Exception as error:  # noqa: BLE001 - que una orden problemática no detenga el cron
                order.message_post(
                    body=_("No se pudo cancelar automáticamente: %s", str(error))
                )
