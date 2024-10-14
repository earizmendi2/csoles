from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hide_margin = fields.Boolean(string='Hide Sale Margin', compute='_compute_for_hide_sale_margin')

    def _compute_for_hide_sale_margin(self):
        for rec in self:
            if self.env.user.has_group("eg_hide_sale_margin.sale_margin_hide_group"):
                rec.hide_margin = False
            else:
                rec.hide_margin = True