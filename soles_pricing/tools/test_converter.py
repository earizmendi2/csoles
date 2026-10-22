import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('converter', Path(__file__).with_name('convert_prototype.py'))
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.mapping = {'company_xmlid': 'base.main_company', 'currency_xmlid': 'base.MXN',
            'clients': {'Cliente': 'example.partner'}, 'families': {'Familia': 'example.family'},
            'brands': {'Marca': 'example.brand'}, 'skus': {'SKU': 'example.product'},
            'profiles': {'Gold': {'segment_xmlid': 'soles_pricing.segment_gold',
                'rule_xmlid': 'example.profile_gold', 'family_xmlid': 'example.family', 'discount_pct': '6.25'}}}
        self.data = {'format': 'soles-client-discounts-v1', 'client': 'Cliente', 'moduleProfile': 'Gold',
                     'rules': [{'id': 'r1', 'category': 'Familia', 'brand': 'Marca', 'skus': 'SKU', 'discount': '2.5'}]}

    def test_explicit_mapping_and_profile_rates(self):
        partners, rules = converter.convert(self.data, self.mapping)
        self.assertEqual(partners[0]['id'], 'example.partner')
        self.assertEqual(rules[0]['product_ids/id'], 'example.product')
        self.assertEqual(rules[1]['discount_pct'], '6.25')
        self.assertEqual(rules[1]['scope'], 'segment')
        self.assertEqual(rules[0]['state'], 'draft')
        self.assertEqual(rules[0]['family_id/id'], 'example.family')

    def test_missing_family_mapping_fails(self):
        self.mapping['families'] = {}
        with self.assertRaisesRegex(ValueError, 'sin mapeo'):
            converter.convert(self.data, self.mapping)

    def test_unknown_sku_fails(self):
        self.mapping['skus'] = {}
        with self.assertRaisesRegex(ValueError, 'sin mapeo'):
            converter.convert(self.data, self.mapping)

    def test_invalid_rates_fail(self):
        for value in ['NaN', 'Infinity', '-1', '101', None]:
            with self.assertRaises(ValueError):
                converter.percent(value)

    def test_repeat_is_stable(self):
        self.assertEqual(converter.convert(self.data, self.mapping), converter.convert(self.data, self.mapping))

    def test_duplicate_partner_fails(self):
        with self.assertRaisesRegex(ValueError, 'mismo contacto'):
            converter.convert({'clients': [self.data, self.data]}, self.mapping)


if __name__ == '__main__':
    unittest.main()
