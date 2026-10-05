# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    excluir_autocancelacion = fields.Boolean(
        string='Excluir de cancelación automática de pedidos',
        help='Si está marcado, ningún pedido de este cliente será '
             'cancelado automáticamente por falta de facturación.')
