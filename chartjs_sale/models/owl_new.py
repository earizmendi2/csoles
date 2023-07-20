from odoo import fields, models


class View(models.Model):
    _inherit = "ir.ui.view"

    type = fields.Selection(
        selection_add=[("very_basic_view", "Very Basic View")]
    )
