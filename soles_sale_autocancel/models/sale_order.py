# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from odoo import _, fields, models

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

        Usa invoice_ids = False (ningún registro de factura generado)
        como criterio de "sin facturar", tal como el script original:
        invoice_status no sirve aquí porque una orden recién confirmada
        con política "cantidades pedidas" queda en 'to invoice' de
        inmediato, aunque nadie haya creado la factura todavía. Además
        deja nota en el chatter de cada pedido y es tolerante a errores
        por pedido individual. Toda la parametrización vive en
        soles.autocancel.config; las excepciones puntuales se marcan con
        el checkbox 'excluir_autocancelacion' en el pedido o el cliente,
        nunca hardcodeadas aquí.
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
            ('excluir_autocancelacion', '=', False),
            ('partner_id.excluir_autocancelacion', '=', False),
            ('date_order', '<=', fecha_limite.strftime('%Y-%m-%d 00:00:00')),
        ]
        # Campos de Studio: solo se agregan al dominio si existen en esta
        # base de datos, para que el módulo no truene en otra instancia.
        if 'x_studio_aplica_remisin' in self._fields:
            dominio.append(('x_studio_aplica_remisin', '!=', True))
        if 'x_studio_entrega_autorizada' in self._fields:
            dominio.append(('x_studio_entrega_autorizada', '!=', True))
        if config.fecha_corte_creacion:
            dominio.append(('create_date', '>=', config.fecha_corte_creacion))

        ordenes = self.search(dominio)

        canceladas = []
        logs_a_crear = []

        for order in ordenes:
            dias = (datetime.now() - order.date_order).days
            if dias < config.dias_limite:
                continue

            motivo = _(
                "Cancelada automáticamente: lleva %(dias)s días confirmada "
                "sin generar ninguna factura (Nada que facturar).",
                dias=dias,
            )

            try:
                if not config.modo_prueba:
                    if config.notificar_por_chatter:
                        order.message_post(body=motivo)
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
                if not config.modo_prueba:
                    order.message_post(
                        body=_("No se pudo cancelar automáticamente: %s",
                               str(e)))

        if logs_a_crear:
            self.env['soles.autocancel.log'].sudo().create(logs_a_crear)

        if canceladas:
            self._notificar_cancelacion(config, canceladas)

        return canceladas

    def _notificar_cancelacion(self, config, canceladas):
        prefijo = '[SIMULACIÓN] ' if config.modo_prueba else ''
        mensaje = (
            f"{prefijo}Los pedidos cancelados fueron: {canceladas} "
            f"el día: {fields.Date.today()}"
        )

        if config.canal_notificacion_id:
            config.canal_notificacion_id.message_post(
                body=mensaje, message_type='comment',
                subtype_xmlid='mail.mt_comment')

        destinatarios = config._get_destinatarios_notificacion()
        if destinatarios:
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=destinatarios.ids,
                subject=_('Pedidos cancelados automáticamente'),
                body=mensaje,
            )
