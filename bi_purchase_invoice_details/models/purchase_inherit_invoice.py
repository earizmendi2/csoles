# -*- coding : utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class PurchaseOrderUpdate(models.Model):
	_inherit = 'purchase.order'

	invoiced_amount = fields.Float(string = 'Invoiced Amount',compute ='_compute_invoiced_amount')
	amount_due = fields.Float(string ='Amount Due', compute ='_computedue')
	paid_amount = fields.Float(string ='Paid Amount', compute ='_computepaid')
	amount_paid_percent = fields.Float(compute = 'action_amount_paid')
	currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.user.company_id.currency_id)

	