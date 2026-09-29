# -*- coding: utf-8 -*-
from odoo import fields, models


class SolesAutocancelLog(models.Model):
    _name = 'soles.autocancel.log'
    _description = 'Historial de Cancelaciones Automáticas de Pedidos'
    _order = 'fecha_cancelacion desc'

    order_id = fields.Many2one(
        'sale.order', string='Pedido', required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', related='order_id.partner_id',
        store=True)
    fecha_cancelacion = fields.Datetime(
        string='Fecha de cancelación', default=fields.Datetime.now,
        required=True)
    dias_sin_facturar = fields.Integer(string='Días sin facturar')
    modo_prueba = fields.Boolean(
        string='¿Fue simulación?',
        help='Si estaba activo el modo simulación, este registro es solo '
             'informativo: el pedido NO fue cancelado realmente.')
