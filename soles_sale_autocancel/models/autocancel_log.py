# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SolesAutocancelLog(models.Model):
    _name = 'soles.autocancel.log'
    _description = 'Historial de Cancelaciones Automáticas de Pedidos'
    _order = 'fecha_cancelacion desc, id desc'

    order_id = fields.Many2one(
        'sale.order', string='Pedido', required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', related='order_id.partner_id',
        store=True)
    fecha_cancelacion = fields.Datetime(
        string='Fecha de ejecución', default=fields.Datetime.now,
        required=True)
    dias_sin_facturar = fields.Integer(string='Días sin facturar')
    origen = fields.Selection(
        selection=[
            ('automatico', 'Automático'),
            ('manual', 'Manual'),
        ],
        string='Origen',
        default='automatico',
        required=True,
        index=True,
        help='Indica si el intento fue lanzado por el cron o manualmente '
             'desde la configuración del módulo.')
    modo_prueba = fields.Boolean(
        string='¿Fue simulación?',
        help='Si estaba activo el modo simulación, este registro es solo '
             'informativo: el pedido NO fue cancelado realmente.')
    estado = fields.Selection(
        selection=[
            ('cancelado', 'Cancelado'),
            ('simulacion', 'Simulación'),
            ('error', 'Error'),
        ],
        string='Resultado',
        default='cancelado',
        required=True,
        index=True,
        help='Resultado del intento de autocancelación para este pedido.')
    detalle = fields.Text(
        string='Detalle',
        help='Motivo de cancelación, información de simulación o mensaje '
             'de error devuelto por Odoo.')

    @api.depends('order_id', 'estado', 'origen')
    def _compute_display_name(self):
        estado_labels = dict(
            self._fields['estado']._description_selection(self.env)
        )
        origen_labels = dict(
            self._fields['origen']._description_selection(self.env)
        )

        for rec in self:
            pedido = rec.order_id.display_name or 'Sin pedido'
            estado = estado_labels.get(rec.estado, 'Sin resultado')
            origen = origen_labels.get(rec.origen, 'Sin origen')
            rec.display_name = f'{pedido} · {estado} · {origen}'

