# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

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
        """Punto de entrada del ir.cron."""
        return self._run_autocancel_ordenes(origen='automatico')

    def _run_autocancel_ordenes(self, origen='automatico', config=None):
        """Ejecuta la lógica común de autocancelación.

        :param origen: ``automatico`` para el cron o ``manual`` para el botón.
        :param config: configuración explícita para ejecución manual. Si no se
            proporciona, se toma la configuración activa más reciente.
        :return: resumen de candidatos/cancelados/simulaciones/errores.
        """
        if origen not in ('automatico', 'manual'):
            origen = 'automatico'

        if config is None:
            config = self.env['soles.autocancel.config'].get_config()

        if not config or not config.activo:
            _logger.info(
                'Autocancelación: no hay configuración activa, se omite.')
            return {
                'candidatos': 0,
                'procesados': 0,
                'cancelados': 0,
                'simulaciones': 0,
                'errores': 0,
            }

        ahora = fields.Datetime.now()
        fecha_limite = ahora - timedelta(days=config.dias_limite)

        dominio = [
            ('state', '=', 'sale'),
            ('invoice_ids', '=', False),
            ('excluir_autocancelacion', '=', False),
            ('partner_id.excluir_autocancelacion', '=', False),
            ('partner_id', 'not in', config.clientes_excluidos_ids.ids),
            ('date_order', '<=', fecha_limite),
        ]

        # Campos de Studio: solo se agregan si existen en esta base.
        if (
            config.excluir_aplica_remision
            and 'x_studio_aplica_remisin' in self._fields
        ):
            dominio.append(('x_studio_aplica_remisin', '!=', True))

        if 'x_studio_entrega_autorizada' in self._fields:
            dominio.append(('x_studio_entrega_autorizada', '!=', True))

        if config.fecha_corte_creacion:
            dominio.append(('create_date', '>=', config.fecha_corte_creacion))

        ordenes = self.search(dominio)

        procesadas = []
        canceladas = []
        logs_a_crear = []

        _logger.info(
            'Autocancelación: inicio. Origen=%s, candidatos=%s, límite=%s, '
            'días=%s, simulación=%s',
            origen, len(ordenes), fecha_limite, config.dias_limite,
            config.modo_prueba,
        )

        for order in ordenes:
            dias = max(0, (ahora - order.date_order).days)

            motivo = _(
                'Cancelada automáticamente: lleva %(dias)s días confirmada '
                'sin generar ninguna factura (Nada que facturar).',
                dias=dias,
            )
            if origen == 'manual':
                motivo = _(
                    'Cancelada mediante ejecución manual del proceso de '
                    'autocancelación: lleva %(dias)s días confirmada sin '
                    'generar ninguna factura (Nada que facturar).',
                    dias=dias,
                )

            if config.modo_prueba:
                procesadas.append(order.name)
                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'origen': origen,
                    'modo_prueba': True,
                    'estado': 'simulacion',
                    'detalle': _(
                        'Pedido candidato. No se modificó porque el modo '
                        'simulación estaba activo.'
                    ),
                })
                continue

            try:
                # Cada pedido queda aislado. Si cualquier automatización falla,
                # se revierte únicamente lo hecho para ese pedido.
                with self.env.cr.savepoint():
                    order_ctx = order.with_context(
                        soles_autocancel=True,
                        soles_autocancel_origen=origen,
                    )

                    if config.notificar_por_chatter:
                        order_ctx.message_post(body=motivo)

                    order_ctx.action_unlock()
                    order_ctx._action_cancel()

                    if 'x_studio_veces_cancelado' in order_ctx._fields:
                        order_ctx.write({
                            'x_studio_veces_cancelado':
                                (order_ctx.x_studio_veces_cancelado or 0) + 1,
                        })

                    # Fuerza recomputes diferidos manteniendo el contexto
                    # soles_autocancel=True para que acciones comerciales puedan
                    # ignorar exclusivamente este proceso técnico.
                    order_ctx.env.flush_all()

                canceladas.append(order.name)
                procesadas.append(order.name)
                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'origen': origen,
                    'modo_prueba': False,
                    'estado': 'cancelado',
                    'detalle': motivo,
                })

            except Exception as exc:
                _logger.exception(
                    'Autocancelación: error cancelando %s: %s',
                    order.name, exc,
                )

                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'origen': origen,
                    'modo_prueba': False,
                    'estado': 'error',
                    'detalle': str(exc),
                })

                if config.notificar_por_chatter:
                    try:
                        with self.env.cr.savepoint():
                            order.with_context(
                                soles_autocancel=True,
                                soles_autocancel_origen=origen,
                            ).message_post(
                                body=_(
                                    'No se pudo cancelar automáticamente: %s',
                                    str(exc),
                                )
                            )
                    except Exception:
                        _logger.exception(
                            'Autocancelación: no se pudo registrar en chatter '
                            'el error del pedido %s.',
                            order.name,
                        )

        if logs_a_crear:
            self.env['soles.autocancel.log'].sudo().create(logs_a_crear)

        if canceladas:
            self._notificar_cancelacion(config, canceladas, origen=origen)

        errores = len([
            log for log in logs_a_crear if log.get('estado') == 'error'
        ])
        simulaciones = len([
            log for log in logs_a_crear if log.get('estado') == 'simulacion'
        ])

        resultado = {
            'candidatos': len(ordenes),
            'procesados': len(procesadas),
            'cancelados': len(canceladas),
            'simulaciones': simulaciones,
            'errores': errores,
        }

        _logger.info(
            'Autocancelación: fin. Origen=%s, candidatos=%s, procesados=%s, '
            'cancelados=%s, simulaciones=%s, errores=%s',
            origen, resultado['candidatos'], resultado['procesados'],
            resultado['cancelados'], resultado['simulaciones'],
            resultado['errores'],
        )

        return resultado

    def _notificar_cancelacion(self, config, canceladas, origen='automatico'):
        etiqueta_origen = 'manual' if origen == 'manual' else 'automática'
        mensaje = (
            f"Ejecución {etiqueta_origen}: los pedidos cancelados fueron: "
            f"{canceladas} el día: {fields.Date.today()}"
        )

        if config.canal_notificacion_id:
            config.canal_notificacion_id.message_post(
                body=mensaje,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        destinatarios = config._get_destinatarios_notificacion()
        if destinatarios:
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=destinatarios.ids,
                subject=_('Pedidos cancelados automáticamente'),
                body=mensaje,
            )
