from odoo import _, models, fields, api
from datetime import datetime


class SaleTarget(models.Model):
    _name = 'sale.target'
    _rec_name = 'x_name'
    _description = 'Para configurar el objetivo de venta en el vendedor'

    x_name = fields.Text(string="Name", required=False)
    x_salesperson_id = fields.Many2one(comodel_name="res.users", string="Salesperson", required=True)
    x_created_by_id = fields.Many2one(comodel_name="res.users", string="Created By", required=False,
                                      default=lambda self: self.env.user)
    x_start_date = fields.Date(string="Fecha de Inicio", required=True)
    x_end_date = fields.Date(string="Fecha Final", required=True)
    #x_start_date = fields.Datetime(string="Fecha de Inicio", required=True, default=datetime.today())
    #x_end_date = fields.Datetime(string="Fecha Final", required=True, default=datetime.today())
    x_condition = fields.Selection(string="Condicion", selection=[('sale_order_confirmed', 'Sale Order Confirmed'),
                                                                  ('invoice_confirmed', 'Invoice Confirmed'), ],
                                   required=True)
    x_target_amount = fields.Float(string="Monto Objetivo USD", required=True)
    x_reached_amount = fields.Float(string="Monto Alcanzado USD", compute="_compute_reached_amount")
    x_reached_amount_mxn = fields.Float(string="Monto Alcanzado MXN")
    x_porc_reached_amount = fields.Float(string="Porcentaje Alcanzado", compute="_compute_porc_reached_amount")
    x_porc_reached_amount_report = fields.Float(string="Porc Monto Alcanzado",group_operator="avg")
    x_reached_amount_report = fields.Float(string="Monto Alcanzado USD")
    x_reached_amount_report_mxn = fields.Float(string="Monto Alcanzado MXN")
    x_different_amount = fields.Float(string="Diferencia de Montos USD")
    x_sale_order_confirmed = fields.Many2many(comodel_name="sale.order", string="Sale Order Confirmed")
    x_invoice_confirmed = fields.Many2many(comodel_name="account.move", string="Invoice Confirmed")

    @api.model
    def create(self, values):
        values['x_name'] = self.env["ir.sequence"].next_by_code('sale.target') or _('New')
        return super(SaleTarget, self).create(values)

    @api.depends('x_target_amount', 'x_reached_amount')
    def _compute_porc_reached_amount(self):
        for record in self:
            porc_reached_amount = 0
            if record.x_target_amount > 0:
                porc_reached_amount = record.x_reached_amount / record.x_target_amount
            record['x_porc_reached_amount'] = porc_reached_amount
            record['x_porc_reached_amount_report'] = porc_reached_amount
            
    @api.depends('x_salesperson_id', 'x_start_date', 'x_end_date', 'x_sale_order_confirmed', 'x_invoice_confirmed')
    def _compute_reached_amount(self):
        for record in self:
            reach_amount = 0
            reach_amount_mxn = 0
            
            if record.x_condition == 'sale_order_confirmed':
                sale_orders_confirmed = self.env['sale.order'].search(
                    [('state', '=', 'sale'), ('user_id', '=', record.x_salesperson_id.id),
                     ('date_order', '>=', record.x_start_date.datetime),
                     ('date_order', '<=', record.x_end_date.datetime)])
                if len(sale_orders_confirmed) > 0:
                    for sale_order in sale_orders_confirmed:
                        reach_amount = reach_amount + sale_order.amount_untaxed
                record['x_sale_order_confirmed'] = sale_orders_confirmed
            elif record.x_condition == 'invoice_confirmed':
                invoices_confirmed = self.env['account.move'].search(
                    [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                     ('invoice_user_id', '=', record.x_salesperson_id.id), ('invoice_date', '>=', record.x_start_date),
                     ('invoice_date', '<=', record.x_end_date)])
                if len(invoices_confirmed) > 0:
                    reach_amount = 0
                    reach_amount_mxn = 0
                    for invoice in invoices_confirmed:
                        reach_amount_mxn = reach_amount_mxn + invoice.amount_untaxed_signed
                        reach_amount = reach_amount + (invoice.amount_untaxed_signed / invoice.x_studio_tipocambio)
                        
                record['x_invoice_confirmed'] = invoices_confirmed
            record['x_reached_amount'] = reach_amount
            record['x_reached_amount_mxn'] = reach_amount_mxn
            record['x_reached_amount_report'] = reach_amount
            record['x_reached_amount_report_mxn'] = reach_amount_mxn
            record['x_different_amount'] = record['x_target_amount'] - record['x_reached_amount']
            
class SaleTargetbyTeam(models.Model):
    _name = 'sale.targetbyteam'
    _rec_name = 'x_name'
    _description = 'Para configurar el objetivo por equipo de ventas'

    x_name = fields.Text(string="Nombre", required=False)
    x_team_id = fields.Many2one(comodel_name="crm.team", string="Equipo de Ventas", required=True)
    x_created_by_id = fields.Many2one(comodel_name="res.users", string="Creado por", required=False,
                                      default=lambda self: self.env.user)
    x_start_date = fields.Date(string="Fecha de Inicio", required=True)
    x_end_date = fields.Date(string="Fecha Final", required=True)
    x_condition = fields.Selection(string="Condicion", selection=[('sale_order_confirmed', 'Sale Order Confirmed'),
                                                                  ('invoice_confirmed', 'Invoice Confirmed'), ],
                                   required=True)
    x_target_amount = fields.Float(string="Monto Objetivo USD", required=True)
    x_reached_amount = fields.Float(string="Monto Alcanzado USD", compute="_compute_reached_amount")
    x_reached_amount_mxn = fields.Float(string="Monto Alcanzado MXN")
    x_porc_reached_amount = fields.Float(string="Porcentaje Alcanzado", compute="_compute_porc_reached_amount")
    x_porc_reached_amount_report = fields.Float(string="Porc Monto Alcanzado",group_operator="avg")
    x_reached_amount_report = fields.Float(string="Monto Alcanzado USD")
    x_reached_amount_report_mxn = fields.Float(string="Monto Alcanzado MXN")
    x_different_amount = fields.Float(string="Diferencia de Montos USD")
    x_sale_order_confirmed = fields.Many2many(comodel_name="sale.order", string="Sale Order Confirmed")
    x_invoice_confirmed = fields.Many2many(comodel_name="account.move", string="Invoice Confirmed")

    @api.model
    def create(self, values):
        values['x_name'] = self.env["ir.sequence"].next_by_code('sale.targetbyteam') or _('New')
        return super(SaleTargetbyTeam, self).create(values)

    @api.depends('x_target_amount', 'x_reached_amount')
    def _compute_porc_reached_amount(self):
        for record in self:
            porc_reached_amount = 0
            if record.x_target_amount > 0:
                porc_reached_amount = record.x_reached_amount / record.x_target_amount
            record['x_porc_reached_amount'] = porc_reached_amount
            record['x_porc_reached_amount_report'] = porc_reached_amount
            
    @api.depends('x_team_id', 'x_start_date', 'x_end_date', 'x_sale_order_confirmed', 'x_invoice_confirmed')
    def _compute_reached_amount(self):
        for record in self:
            reach_amount = 0
            reach_amount_mxn = 0
            
            if record.x_condition == 'sale_order_confirmed':
                sale_orders_confirmed = self.env['sale.order'].search(
                    [('state', '=', 'sale'), ('team_id', '=', record.x_team_id.id),
                     ('date_order', '>=', record.x_start_date.datetime),
                     ('date_order', '<=', record.x_end_date.datetime)]) 
                if len(sale_orders_confirmed) > 0:
                    for sale_order in sale_orders_confirmed:
                        reach_amount = reach_amount + sale_order.amount_untaxed
                record['x_sale_order_confirmed'] = sale_orders_confirmed
            elif record.x_condition == 'invoice_confirmed':
                invoices_confirmed = self.env['account.move'].search(
                    [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                     ('team_id', '=', record.x_team_id.id), ('invoice_date', '>=', record.x_start_date),
                     ('invoice_date', '<=', record.x_end_date)])
                if len(invoices_confirmed) > 0:
                    reach_amount = 0
                    reach_amount_mxn = 0
                    for invoice in invoices_confirmed:
                        reach_amount_mxn = reach_amount_mxn + invoice.amount_untaxed_signed
                        reach_amount = reach_amount + (invoice.amount_untaxed_signed / invoice.x_studio_tipocambio)
                        
                record['x_invoice_confirmed'] = invoices_confirmed
            record['x_reached_amount'] = reach_amount
            record['x_reached_amount_mxn'] = reach_amount_mxn
            record['x_reached_amount_report'] = reach_amount
            record['x_reached_amount_report_mxn'] = reach_amount_mxn
            record['x_different_amount'] = record['x_target_amount'] - record['x_reached_amount']



