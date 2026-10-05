# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


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
    clientes_excluidos_ids = fields.Many2many(
        'res.partner',
        'soles_autocancel_config_partners_rel',
        'config_id', 'partner_id',
        string='Clientes excluidos de cancelación automática',
        help='Ningún pedido de estos clientes se cancelará '
             'automáticamente, sin importar cuántos días lleve sin '
             'facturar. Equivalente a marcar el checkbox de exclusión '
             'en la ficha del cliente, pero administrable desde un solo '
             'lugar.')
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
    excluir_aplica_remision = fields.Boolean(
        string='No cancelar pedidos que aplican remisión',
        default=True,
        help='Si está activo (recomendado), los pedidos marcados con '
             '"Aplica remisión" nunca se cancelan automáticamente, sin '
             'importar los días sin facturar. Desactívalo si quieres que '
             'el cron también los considere.')
    modo_prueba = fields.Boolean(
        string='Modo simulación',
        default=False,
        help='Si está activo, el cron y la ejecución manual solo registran '
             'en la bitácora qué pedidos cancelarían, pero no cancelan nada '
             'real ni notifican a nadie.')

    @api.constrains('dias_limite')
    def _check_dias_limite(self):
        for rec in self:
            if rec.dias_limite < 0:
                raise UserError(_('Los días límite no pueden ser negativos.'))

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

    def action_run_autocancel(self):
        """Ejecuta manualmente la misma lógica utilizada por el cron."""
        self.ensure_one()

        puede_ejecutar = (
            self.env.user.has_group(
                'soles_sale_autocancel.group_autocancel_manual'
            )
            or self.env.user.has_group('sales_team.group_sale_manager')
        )
        if not puede_ejecutar:
            raise AccessError(_(
                'No tienes permisos para ejecutar manualmente la '
                'cancelación automática de pedidos.'
            ))

        if not self.activo:
            raise UserError(_(
                'La configuración está desactivada. Actívala antes de '
                'ejecutar la cancelación manual.'
            ))

        resultado = self.env['sale.order'].sudo()._run_autocancel_ordenes(
            origen='manual',
            config=self.sudo(),
        )

        message = _(
            'Proceso finalizado. Candidatos: %(candidatos)s | '
            'Cancelados: %(cancelados)s | Simulaciones: %(simulaciones)s | '
            'Errores: %(errores)s',
            candidatos=resultado['candidatos'],
            cancelados=resultado['cancelados'],
            simulaciones=resultado['simulaciones'],
            errores=resultado['errores'],
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Autocancelación finalizada'),
                'message': message,
                'type': 'warning' if resultado['errores'] else 'success',
                'sticky': bool(resultado['errores']),
            },
        }
