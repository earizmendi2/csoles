# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class CustomSaleorderProductOnhandQty(models.TransientModel):
    _name = 'custom.saleorder.product.onhand.qty'
    _description = "Custom Saleorder Product Onhand Qty"

    tabel_body = fields.Html(
        string="HTML",
        readonly = True
    )

