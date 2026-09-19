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
             'pedidos cancelados. Si se deja vacío, no se publica en '
             'ningún canal.')
    notificar_usuario_ids = fields.Many2many(
        'res.users',
        'soles_autocancel_config_users_rel',
        'config_id', 'user_id',
        string='Notificar a estos usuarios',
        help='Estos usuarios reciben una notificación directa (bandeja de '
             'entrada de Odoo) cada vez que se cancelan pedidos.')
    notificar_grupo_ids = fields.Many2many(
        'res.groups',
        'soles_autocancel_config_groups_rel',
        'config_id', 'group_id',
        string='Notificar a estos grupos',
        help='Todos los usuarios que pertenezcan a estos grupos de '
             'seguridad reciben la notificación. Como se resuelve al '
             'momento de ejecutar el cron, si mañana alguien entra o sale '
             'del grupo, la lista de destinatarios se ajusta sola.')
    notificar_por_chatter = fields.Boolean(
        string='Anotar motivo en el chatter de cada pedido',
        default=True,
        help='Si está activo, cada pedido cancelado recibe una nota en su '
             'propio chatter explicando por qué se canceló.')
    modo_prueba = fields.Boolean(
        string='Modo simulación',
        default=False,
        help='Si está activo, el cron solo registra en la bitácora qué '
             'pedidos cancelaría, pero no los cancela realmente ni '
             'notifica a nadie.')

    @api.model
    def get_config(self):
        """Devuelve la configuración activa más reciente, o None."""
        return self.search([('activo', '=', True)], limit=1, order='id desc')

    def _get_destinatarios_notificacion(self):
        """Resuelve usuarios + grupos a un recordset de res.partner único."""
        self.ensure_one()
        partners = self.notificar_usuario_ids.mapped('partner_id')
        for grupo in self.notificar_grupo_ids:
            partners |= grupo.users.mapped('partner_id')
        return partners
