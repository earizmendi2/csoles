from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    valuation_value = fields.Float(string='Valuation Value', compute='_compute_valuation_value',store=True)

    def _compute_valuation_value(self):
        for line in self:
            valuation_layers = self.env['stock.valuation.layer'].search(
                [('stock_move_id', '=', line.move_id.id), ('product_id', '=', line.product_id.id)])
            # replace 'stock_move_id' and 'product_id' with the actual field names for the corresponding fields in the 'stock.valuation.layer' table

            line.valuation_value = sum([layer.value for layer in valuation_layers])
            # replace 'value' with the actual field name for the value column in the 'stock.valuation.layer' table
