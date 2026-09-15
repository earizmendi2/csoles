from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_auto_cancel_days = fields.Integer(
        string='Cancelar automáticamente órdenes sin facturar después de (días)',
        config_parameter='sale_auto_cancel.days',
        help=(
            'Las órdenes de venta confirmadas sin ninguna factura asociada '
            '(Nada que facturar) se cancelarán automáticamente si llevan más '
            'de este número de días desde su creación. 0 desactiva la '
            'cancelación automática.'
        ),
    )
