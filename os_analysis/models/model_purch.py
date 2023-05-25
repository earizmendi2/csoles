# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    state = fields.Selection(string="Status", related="order_id.state", store=True)
    date_order = fields.Datetime(string="Order Date", related="order_id.date_order", store=True)

    partner_id = fields.Many2one('res.partner', string='Customer', related="order_id.partner_id", store=True)
    product_tmpl_id_name = fields.Char(string='Balance', related="product_id.product_tmpl_id.name", store=True)


    # pricelist_id = fields.Many2one(
    #     string="Pricelist",
    #     related="order_id.pricelist_id", store=True)

    # image_1920 = fields.Image(string='immmmg', related="product_id.product_tmpl_id.image_1920", store=True)

