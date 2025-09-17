# -*- coding: utf-8 -*-
from odoo import fields, models


class AddSuggestedProduce(models.TransientModel):
    _name = 'add.suggested.product.wizard'

    suggested_product_ids = fields.One2many('auto.suggested.line', 'suggested_product_id', string='Suggested Products')

    def add(self):
        active_id = self._context.get('active_id')
        for suggested_product_id in self.suggested_product_ids:
            if suggested_product_id.quantity > 0:
                sale_order_line = self.env['sale.order.line'].create({
                    'order_id': int(active_id),
                    'product_id': suggested_product_id.product_id.id,
                    'name': suggested_product_id.product_id.name,
                    'product_uom_qty': suggested_product_id.quantity,
                    'state': 'sale',
                    'price_unit': suggested_product_id.product_id.lst_price
                })
                sale_order_line.product_id_change()


class AutoSuggestedLine(models.TransientModel):
    _name = 'auto.suggested.line'

    suggested_product_id = fields.Many2one('add.suggested.product.wizard')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=0.0)
    price_unit = fields.Float(string='Unit Price')
