from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.template'

    expected_sales = fields.Float(string='Expected Sales this month', compute='_compute_expected_sales')

    def _compute_expected_sales(self):
        for product in self:
            last_year_start = datetime.now() - relativedelta(years=1 )
            last_year_end = datetime.now() - relativedelta(years=1) +  relativedelta(  months=1)

            last_year_month_sales = sum(self.env['sale.order.line'].search([
                ('order_id.date_order', '>=', last_year_start.date()),
                 ('order_id.date_order', '<', last_year_end.date()),
                ('product_id', '=', product.id),
                 ('order_id.state', 'in', ('sale', 'done', 'draft'))
            ]).mapped('product_uom_qty'))

            # avg_monthly_sales = last_year_month_sales / 12
            # expected_sales = avg_monthly_sales  # + this_month_sales
            expected_sales = last_year_month_sales  # + this_month_sales

            product.expected_sales = expected_sales
