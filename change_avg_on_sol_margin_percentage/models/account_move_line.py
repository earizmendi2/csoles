from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_margen_porcentaje = fields.Float(
        string='Margen %%',
        store=True,
        group_operator="avg"
    )