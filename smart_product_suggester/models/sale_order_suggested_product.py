# -*- coding: utf-8 -*-
import csv
import pickle

from efficient_apriori import apriori

from odoo import models


def power_set(s):
    x = len(s)
    masks = [1 << i for i in range(x)]
    for i in range(1 << x):
        yield [ss for mask, ss in zip(masks, s) if i & mask]


class ProductProduct(models.Model):
    _inherit = "sale.order"

    def get_suggestions(self):
        records = []
        try:
            with open("data.pickle", "rb") as f:
                rules = pickle.load(f)
        except:
            with open('large.csv') as csv_file:
                data = csv.reader(csv_file, delimiter=',')
                for row in data:
                    records.append(row)
            ICPSudo = self.env['ir.config_parameter'].sudo()
            min_supp = float(ICPSudo.get_param('smart_product_suggester.min_support')) / 100
            min_conf = float(ICPSudo.get_param('smart_product_suggester.min_confidence')) / 100
            item_sets, rules = apriori(records, min_support=min_supp, min_confidence=min_conf)

            with open("data.pickle", "wb") as f:
                pickle.dump(rules, f)
        sale_order_line_init_products = set()
        to_add_product_ids = set()

        for rec in self:
            for item in rec.order_line:
                sale_order_line_init_products.add(item.product_id.id)
        sub_sets = list(power_set(sale_order_line_init_products))
        sub_sets.sort(key=len, reverse=True)
        for sub_set in sub_sets:
            for rule in rules:
                int_value = []
                for value in rule.lhs:
                    int_value.append(int(value))
                if set(sub_set) == set(int_value):
                    for value_rhs in rule.rhs:
                        if int(value_rhs) not in list(sale_order_line_init_products):
                            to_add_product_ids.add(int(value_rhs))

        order_items = []
        for order_item in to_add_product_ids:
            product = self.env['product.product'].browse(order_item)
            order_items.append([0, 0, {
                'product_id': order_item,
                'price_unit': product.lst_price,
                'quantity': 0.0
            }])
        res_id = (
            self.env['add.suggested.product.wizard'].create({'suggested_product_ids': order_items})).id
        return {
            'name': 'Suggested Products',
            'type': 'ir.actions.act_window',
            'res_model': 'add.suggested.product.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': False,
            'res_id': res_id,
            'target': 'new',
        }
