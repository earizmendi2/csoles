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
        """Cancela pedidos confirmados sin facturar tras N días.

        v1.4:
        - Usa un contexto específico ``soles_autocancel=True`` para que las
          automatizaciones comerciales puedan ignorar exclusivamente este
          proceso técnico.
        - Cada pedido se procesa dentro de un SAVEPOINT. Si una automatización
          o cualquier otro código falla, se revierte únicamente ese pedido y
          el cron continúa con los demás.
        - Fuerza el ``flush_all`` dentro del contexto de autocancelación para
          que los recomputes diferidos (por ejemplo qty_to_invoice) y las
          acciones automatizadas asociadas se ejecuten todavía con ese
          contexto, evitando que fallen después de salir del try/except.
        - No hace commits manuales. La transacción global queda bajo control
          de ir.cron/Odoo.
        - El umbral se calcula con Datetime: N días = N x 24 horas.
        - Registra en la bitácora cancelaciones, simulaciones y errores.
        """
        config = self.env['soles.autocancel.config'].get_config()
        if not config:
            _logger.info(
                'Autocancelación: no hay configuración activa, se omite.')
            return []

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

        # Campos de Studio: solo se agregan al dominio si existen en esta
        # base de datos, para que el módulo no falle en otra instancia.
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
            'Autocancelación: inicio. Candidatos=%s, límite=%s, '
            'días=%s, simulación=%s',
            len(ordenes), fecha_limite, config.dias_limite, config.modo_prueba,
        )

        for order in ordenes:
            # date_order es Datetime. El dominio ya garantizó que cumple el
            # umbral; este cálculo se conserva para auditoría/bitácora.
            dias = max(0, (ahora - order.date_order).days)

            motivo = _(
                'Cancelada automáticamente: lleva %(dias)s días confirmada '
                'sin generar ninguna factura (Nada que facturar).',
                dias=dias,
            )

            # En simulación no tocamos el pedido; únicamente dejamos evidencia.
            if config.modo_prueba:
                procesadas.append(order.name)
                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'modo_prueba': True,
                    'estado': 'simulacion',
                    'detalle': _(
                        'Pedido candidato. No se modificó porque el modo '
                        'simulación estaba activo.'
                    ),
                })
                continue

            try:
                # Un fallo debe revertir únicamente este pedido, no dejar
                # cancelaciones parciales ni contaminar el resto del cron.
                with self.env.cr.savepoint():
                    order_ctx = order.with_context(soles_autocancel=True)

                    if config.notificar_por_chatter:
                        order_ctx.message_post(body=motivo)

                    # Se conserva el comportamiento original del módulo.
                    # action_unlock es idempotente para pedidos bloqueados y es
                    # requerido en la configuración actual de Soles.
                    order_ctx.action_unlock()
                    order_ctx._action_cancel()

                    if 'x_studio_veces_cancelado' in order_ctx._fields:
                        order_ctx.write({
                            'x_studio_veces_cancelado':
                                (order_ctx.x_studio_veces_cancelado or 0) + 1,
                        })

                    # CRÍTICO: las acciones automatizadas pueden dispararse al
                    # recomputar campos al final del cron. Se fuerza aquí el
                    # flush mientras sigue vigente soles_autocancel=True, de
                    # modo que esas acciones puedan reconocer el contexto.
                    order_ctx.env.flush_all()

                canceladas.append(order.name)
                procesadas.append(order.name)
                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'modo_prueba': False,
                    'estado': 'cancelado',
                    'detalle': motivo,
                })

            except Exception as exc:
                # _logger.exception conserva el traceback completo del pedido
                # que falló, pero el SAVEPOINT ya revirtió sus cambios.
                _logger.exception(
                    'Autocancelación: error cancelando %s: %s',
                    order.name, exc,
                )

                logs_a_crear.append({
                    'order_id': order.id,
                    'dias_sin_facturar': dias,
                    'modo_prueba': False,
                    'estado': 'error',
                    'detalle': str(exc),
                })

                # El aviso en chatter es secundario: nunca debe provocar que
                # el cron completo falle si por alguna razón no puede crearse.
                if config.notificar_por_chatter:
                    try:
                        with self.env.cr.savepoint():
                            order.with_context(
                                soles_autocancel=True
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
            # La bitácora se crea fuera de los savepoints de cada pedido para
            # conservar el diagnóstico incluso cuando una cancelación falle.
            self.env['soles.autocancel.log'].sudo().create(logs_a_crear)

        if canceladas:
            self._notificar_cancelacion(config, canceladas)

        _logger.info(
            'Autocancelación: fin. Candidatos=%s, procesados=%s, '
            'cancelados=%s, errores=%s, simulación=%s',
            len(ordenes), len(procesadas), len(canceladas),
            len([log for log in logs_a_crear if log.get('estado') == 'error']),
            config.modo_prueba,
        )

        return procesadas

    def _notificar_cancelacion(self, config, canceladas):
        mensaje = (
            f"Los pedidos cancelados fueron: {canceladas} "
            f"el día: {fields.Date.today()}"
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
