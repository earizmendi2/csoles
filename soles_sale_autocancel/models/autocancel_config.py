# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SolesAutocancelConfig(models.Model):
    _name = 'soles.autocancel.config'
    _description = 'Configuración de Cancelación Automática de Pedidos'

    name = fields.Char(default='Configuración General', required=True)
    activo = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desmarcado, el cron no cancelará ningún pedido.')
    dias_limite = fields.Integer(
        string='Días sin facturar antes de cancelar',
        default=3, required=True)
    fecha_corte_creacion = fields.Date(
        string='Ignorar pedidos creados antes de',
        default='2024-01-01',
        help='Pedidos creados antes de esta fecha nunca se evalúan.')
    canal_notificacion_id = fields.Many2one(
        'discuss.channel',
        string='Canal de notificación',
        help='Canal de Discuss donde se publica el resumen diario de '
             'pedidos cancelados. Si se deja vacío, no se notifica.')
    modo_prueba = fields.Boolean(
        string='Modo simulación',
        default=False,
        help='Si está activo, el cron solo registra en la bitácora qué '
             'pedidos cancelaría, pero no los cancela realmente.')

    @api.model
    def get_config(self):
        """Devuelve la configuración activa más reciente, o None."""
        return self.search([('activo', '=', True)], limit=1, order='id desc')
