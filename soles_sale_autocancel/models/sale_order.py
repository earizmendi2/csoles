# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    excluir_autocancelacion = fields.Boolean(
        string='Excluir de cancelación automática',
        tracking=True,
        help='Si está marcado, este pedido nunca será cancelado '
             'automáticamente, sin importar cuántos días lleve sin '
             'facturar.')

    def _cron_autocancel_ordenes(self):
        """Cancela pedidos confirmados sin facturar tras N días.

        Reemplaza la Acción Programada original. Toda la parametrización
        vive en soles.autocancel.config; las excepciones puntuales se
        marcan con el checkbox 'excluir_autocancelacion' en el pedido o
        en el cliente, en vez de hardcodearse aquí.
        """
        config = self.env['soles.autocancel.config'].get_config()
        if not config:
            _logger.info(
                'Autocancelación: no hay configuración activa, se omite.')
            return

        fecha_limite = fields.Date.today() - timedelta(days=config.dias_limite)
        dominio = [
            ('state', '=', 'sale'),
            ('invoice_ids', '=', False),
            ('x_studio_aplica_remisin', '!=', True),
            ('x_studio_entrega_autorizada', '!=', True),
            ('excluir_autocancelacion', '=', False),
            ('partner_id.excluir_autocancelacion', '=', False),
            ('create_date', '>=', config.fecha_corte_creacion),
            ('date_order', '<=', fecha_limite.strftime('%Y-%m-%d 00:00:00')),
        ]
        ordenes = self.search(dominio)

        canceladas = []
        logs_a_crear = []

        for order in ordenes:
            dias = (datetime.now() - order.date_order).days
            if dias < config.dias_limite:
                continue

            try:
                if not config.modo_prueba:
                    order.action_unlock()
                    order._action_cancel()
                    if 'x_studio_veces_cancelado' in order._fields:
                        order.write({
                            'x_studio_veces_cancelado':
                                (order.x_studio_veces_cancelado or 0) + 1,
                        })
                    self.env.cr.commit()

                canceladas.append(order.name)
                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'modo_prueba': config.modo_prueba,
                })
            except Exception as e:
                _logger.error(
                    'Autocancelación: error cancelando %s: %s',
                    order.name, e)

        if logs_a_crear:
            self.env['soles.autocancel.log'].sudo().create(logs_a_crear)

        if canceladas and config.canal_notificacion_id:
            prefijo = '[SIMULACIÓN] ' if config.modo_prueba else ''
            mensaje = (
                f"{prefijo}Los pedidos cancelados fueron: {canceladas} "
                f"el día: {fields.Date.today()}"
            )
            config.canal_notificacion_id.message_post(
                body=mensaje, message_type='comment',
                subtype_xmlid='mail.mt_comment')

        return canceladas
