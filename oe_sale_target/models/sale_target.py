from odoo import _, models, fields, api
from datetime import datetime


class SaleTarget(models.Model):
    _name = 'sale.target'
    _rec_name = 'x_name'
    _description = 'To setup the sale target on salesperson'

    x_name = fields.Text(string="Name", required=False)
    x_salesperson_id = fields.Many2one(comodel_name="res.users", string="Salesperson", required=True)
    x_created_by_id = fields.Many2one(comodel_name="res.users", string="Created By", required=False,
                                      default=lambda self: self.env.user)
    x_start_date = fields.Datetime(string="Start Date", required=True, default=datetime.today())
    x_end_date = fields.Datetime(string="End Date", required=True, default=datetime.today())
    x_condition = fields.Selection(string="Condition", selection=[('sale_order_confirmed', 'Sale Order Confirmed'),
                                                                  ('invoice_confirmed', 'Invoice Confirmed'), ],
                                   required=True)
    x_target_amount = fields.Float(string="Target Amount", required=True)
    x_reached_amount = fields.Float(string="Reached Amount", compute="_compute_reached_amount")
    x_reached_amount_report = fields.Float(string="Reached Amount")
    x_different_amount = fields.Float(string="Different Amount")
    x_sale_order_confirmed = fields.Many2many(comodel_name="sale.order", string="Sale Order Confirmed")
    x_invoice_confirmed = fields.Many2many(comodel_name="account.move", string="Invoice Confirmed")

    @api.model
    def create(self, values):
        values['x_name'] = self.env["ir.sequence"].next_by_code('sale.target') or _('New')
        return super(SaleTarget, self).create(values)

    @api.depends('x_salesperson_id', 'x_start_date', 'x_end_date', 'x_sale_order_confirmed', 'x_invoice_confirmed')
    def _compute_reached_amount(self):
        for record in self:
            reach_amount = 0
            if record.x_condition == 'sale_order_confirmed':
                sale_orders_confirmed = self.env['sale.order'].search(
                    [('state', '=', 'sale'), ('user_id', '=', record.x_salesperson_id.id),
                     ('date_order', '>=', record.x_start_date),
                     ('date_order', '<=', record.x_end_date)])
                if len(sale_orders_confirmed) > 0:
                    for sale_order in sale_orders_confirmed:
                        reach_amount = reach_amount + sale_order.amount_total
                record['x_sale_order_confirmed'] = sale_orders_confirmed
            elif record.x_condition == 'invoice_confirmed':
                invoices_confirmed = self.env['account.move'].search(
                    [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                     ('invoice_user_id', '=', record.x_salesperson_id.id), ('invoice_date', '>=', record.x_start_date),
                     ('invoice_date', '<=', record.x_end_date)])
                if len(invoices_confirmed) > 0:
                    for invoice in invoices_confirmed:
                        reach_amount = reach_amount + invoice.amount_total_signed
                record['x_invoice_confirmed'] = invoices_confirmed
            record['x_reached_amount'] = reach_amount
            record['x_reached_amount_report'] = reach_amount
            record['x_different_amount'] = record['x_target_amount'] - record['x_reached_amount']



