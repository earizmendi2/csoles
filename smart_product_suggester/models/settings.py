# -*- coding: utf-8 -*-
import csv
import os
import pickle

from efficient_apriori import apriori

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleFrequentSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    min_support = fields.Float(string='Minimum Support Value (%)')
    min_confidence = fields.Float(string='Minimum Confidence Value (%)')

    def set_values(self):
        res = super(SaleFrequentSettings, self).set_values()

        self.env['ir.config_parameter'].set_param('smart_product_suggester.min_support', self.min_support)
        self.env['ir.config_parameter'].set_param('smart_product_suggester.min_confidence', self.min_confidence)
        return res

    @api.model
    def get_values(self):
        res = super(SaleFrequentSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        min_support = float(ICPSudo.get_param('smart_product_suggester.min_support')) or 8.0
        min_confidence = float(ICPSudo.get_param('smart_product_suggester.min_confidence')) or 50.0

        res.update(
            min_support=min_support,
            min_confidence=min_confidence,
        )
        return res

    @api.onchange('min_support', 'min_confidence')
    def _check_values(self):
        if self.min_support < 0.0 or self.min_support > 100.0:
            raise ValidationError(_('Minimum Support must be between 0-100'))
        if self.min_confidence < 0.0 or self.min_confidence > 100.0:
            raise ValidationError(_('Minimum Confidence must be between 0-100'))

    def update_knowledge_base(self):
        if os.path.isfile('data.pickle'):
            os.remove('data.pickle')
        self._cr.execute("""select order_id
                            from sale_order_line
                            group by order_id;
                        """)
        data = self._cr.fetchall()
        with open('large.csv', 'w') as f1:
            writer = csv.writer(f1, delimiter=',', lineterminator='\n', )
            for order in data:
                row = []
                self._cr.execute("""select product_id
                                    from sale_order_line
                                    where order_id = %d
                                        """ % (order[0]))
                items = self._cr.fetchall()
                for item in items:
                    row.append(int(item[0]))
                writer.writerow(row)
        if os.path.isfile('large.csv'):
            records = []
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
