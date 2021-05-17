# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    custom_check_onhand_qty = fields.Boolean(
    	string="Sales Order Alert",
        help="If qty not in hand at warehouse then raise alert on confirm sales time ."
    )

