from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    colony = fields.Char(
        string='Colonia',
        help=(
            'Colonia del domicilio fiscal. Si este campo existe, '
            'cs_partner_tax_certificate lo usa en vez de "Calle 2" al '
            'importar o actualizar la Constancia de Situación Fiscal.'
        ),
    )
