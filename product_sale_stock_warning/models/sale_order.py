# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_check_onhand_qty = fields.Boolean(
        string="Forcefully Confirm",
        help="Confirm the sales order without checking the quantity.",
    )

    def action_confirm(self):
        if self._context.get('website_id'):
            return super(SaleOrder, self).action_confirm()
        else:
            for rec in self:
                line_ids = self.env['sale.order.line']
                for line in rec.order_line:
                    if not line.order_id.custom_check_onhand_qty and line.product_id.product_tmpl_id.custom_check_onhand_qty and line.product_type == 'product':
                        if line.virtual_available_at_date < line.qty_to_deliver and not line.is_mto:
                            line_ids += line
                if line_ids:
                    tabel_body = """
                        <table class="table" style="width:100%">
                            <thead class="thead-dark">
                                <tr>
                                    <th style="width: 3%">#</th>
                                    <th style="width: 67%">Product</th>
                                    <th style="width: 10%">Requested Quantity</th>
                                    <th style="width: 10%">Forecasted Stock</th>
                                    <th style="width: 10%">Available Stock</th>
                                </tr>
                            </thead>
                    """
                    line_count = 1
                    for line in line_ids:
                        tabel_tr = "<tr><td>" + str(line_count) + "</td>"
                        tabel_tr += "<td>" + str(line.product_id.display_name) + "</td>"
                        tabel_tr += "<td>" + str(line.product_uom_qty) + ' ' + str(line.product_uom.display_name) + "</td>"
                        tabel_tr += "<td>" + str(line.virtual_available_at_date) + ' ' + str(line.product_uom.display_name) + "</td>"
                        tabel_tr += "<td>" + str(line.free_qty_today) + ' ' + str(line.product_uom.display_name) + "</td>"
                        tabel_body = tabel_body + ' ' + tabel_tr
                        line_count += 1
                    
                    tabel_body = tabel_body + '' + """
                        </table>
                    """
                    ctx = {
                        'default_tabel_body': tabel_body
                    }
                    return {
                        'name': _('Product Quantity Availibilty Warning'),
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'custom.saleorder.product.onhand.qty',
                        'views': [(False, 'form')],
                        'view_id': False,
                        'target': 'new',
                        'context': ctx,
                    }
            return super(SaleOrder, self).action_confirm()

