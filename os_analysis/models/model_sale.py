# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    commitment_date = fields.Datetime(string="Delivery Date", related="order_id.commitment_date", store=True)
    date_order = fields.Datetime(string="Order Date", related="order_id.commitment_date", store=True)

    partner_id = fields.Many2one('res.partner', string='Customer', related="order_id.partner_id", store=True)
    product_tmpl_id_name = fields.Char(string='Balance', related="product_id.product_tmpl_id.name", store=True)

    partner_invoice_id = fields.Many2one(
        comodel_name='res.partner', related="order_id.partner_invoice_id", store=True)

    pricelist_id = fields.Many2one(
        string="Pricelist",
        related="order_id.pricelist_id", store=True)

    category_id = fields.Many2one('product.category', string='Product Category', related='product_id.categ_id', store=True)
    # image_1920 = fields.Image(string='immmmg', related="product_id.product_tmpl_id.image_1920", store=True)

