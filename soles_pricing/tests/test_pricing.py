from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.soles_pricing.models.math import net_price, margin, cost_price


@tagged('post_install', '-at_install')
class TestSolesPricing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Isolate fixtures from pre-existing rules in a staging database; the
        # test transaction rolls these changes back with the rest of the suite.
        for model in ('soles.pricing.rule', 'soles.pricing.authority'):
            cls.env[model].search([('company_id', '=', cls.company.id)]).write({'active': False})
        cls.seller = cls._user('soles_seller', ['soles_pricing.group_seller'])
        cls.manager = cls._user('soles_manager', ['soles_pricing.group_manager'])
        cls.approver = cls._user('soles_approver', ['soles_pricing.group_approver'])
        cls.other = cls._user('soles_other', ['soles_pricing.group_seller'])
        cls.segment = cls.env.ref('soles_pricing.segment_gold')
        cls.segment.write({'active': True})
        cls.brand = cls.env['soles.pricing.brand'].create({'name': 'Marca pruebas'})
        cls.category = cls.env['product.category'].create({'name': 'Familia pruebas'})
        cls.child = cls.env['product.category'].create({'name': 'Subfamilia', 'parent_id': cls.category.id})
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Gold', 'soles_segment_id': cls.segment.id})
        cls.product = cls.env['product.product'].create({
            'name': 'SKU de prueba', 'default_code': 'SOLES-TEST', 'list_price': 1500,
            'standard_price': 1150, 'categ_id': cls.child.id, 'soles_brand_id': cls.brand.id,
            'taxes_id': [Command.clear()]})
        cls.pricelist = cls.env['product.pricelist'].create({'name': 'Lista pruebas', 'currency_id': cls.company.currency_id.id, 'company_id': cls.company.id})
        cls.base_rule = cls.env['soles.pricing.rule'].create({
            'name': 'Gold por familia', 'scope': 'segment', 'segment_id': cls.segment.id,
            'category_id': cls.category.id, 'method': 'fixed', 'fixed_price': 1350,
            'currency_id': cls.company.currency_id.id})
        cls.benefit = cls.env['soles.pricing.rule'].create({
            'name': 'Beneficio cliente', 'scope': 'partner', 'partner_id': cls.partner.id,
            'stage': 'benefit', 'discount_pct': 2})
        cls.seller_auth = cls.env['soles.pricing.authority'].create({
            'name': 'Facultad vendedor', 'operation': 'discount',
            'group_id': cls.env.ref('soles_pricing.group_seller').id, 'max_discount': 3})
        cls.approver_auth = cls.env['soles.pricing.authority'].create({
            'name': 'Facultad aprobar', 'operation': 'approve',
            'user_id': cls.approver.id, 'max_discount': 10, 'min_margin': 5, 'override_floor': True})
        cls.cost = cls.env['soles.pricing.cost'].create({
            'name': 'Costo prueba', 'product_id': cls.product.id, 'amount': 1150,
            'currency_id': cls.company.currency_id.id, 'date_start': fields.Date.today() - timedelta(days=30)})
        cls.company.write({'soles_pricing_mode': 'enforce', 'soles_discount_mode': 'additive',
                           'soles_min_margin': 0, 'soles_require_cost': True,
                           'soles_allow_self_approval': False, 'soles_approval_hours': 24})

    @classmethod
    def _user(cls, login, groups):
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': login + '@example.invalid', 'company_id': cls.company.id,
            'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(g).id for g in groups])]})

    def _order(self, price=None, user=None, lines=1):
        user = user or self.seller
        order = self.env['sale.order'].with_user(user).create({
            'partner_id': self.partner.id, 'pricelist_id': self.pricelist.id, 'user_id': user.id,
            'company_id': self.company.id,
            'order_line': [Command.create(dict(
                product_id=self.product.id, product_uom_qty=1, product_uom=self.product.uom_id.id,
                tax_id=[Command.clear()], **({'price_unit': price} if price is not None else {}))) for _ in range(lines)]})
        return order

    def _request(self, line):
        line.write({'soles_request_reason': 'Proyecto especial con precio exacto'})
        action = line.action_soles_request()
        return self.env['soles.pricing.approval'].browse(action['res_id'])

    def _approve(self, line):
        rec = self._request(line)
        rec.with_user(self.approver).action_approve()
        return rec

    def test_01_historical_example(self):
        order = self._order()
        line = order.order_line
        self.assertAlmostEqual(line.price_unit, 1323)
        ev = line._soles_evaluate()
        self.assertAlmostEqual(ev['base'], 1350)
        self.assertAlmostEqual(ev['min_price'], 1282.5)
        line.write({'price_unit': 1250})
        ev = line._soles_evaluate()
        self.assertAlmostEqual(ev['margin'], 8)
        self.assertTrue(ev['needs_approval'])
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_confirm()
        approval = self._approve(line)
        self.assertTrue(approval.effective_valid)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(approval.state, 'consumed')
        self.assertTrue(approval.consumed_at)

    def test_02_discount_within_authority(self):
        order = self._order(1282.5)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.soles_approval_ids)

    def test_03_approving_and_discounting_are_separate(self):
        order = self._order(1250)
        rec = self._request(order.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint():
            rec.with_user(self.manager).action_approve()
        # Approver group alone does not grant a numeric discount authority.
        other = self._order(1300, user=self.approver)
        self.assertTrue(other.order_line._soles_evaluate()['needs_approval'])

    def test_04_no_self_approval(self):
        order = self._order(1250, user=self.approver)
        rec = self._request(order.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint():
            rec.with_user(self.approver).action_approve()

    def test_05_line_change_and_restore_invalidates(self):
        order = self._order(1250)
        rec = self._approve(order.order_line)
        order.order_line.write({'price_unit': 1249})
        order.order_line.write({'price_unit': 1250})
        self.assertEqual(rec.state, 'invalid')
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_confirm()

    def test_06_quote_changes_invalidate(self):
        order = self._order(1250)
        rec = self._approve(order.order_line)
        order.write({'payment_term_id': self.env.ref('account.account_payment_term_immediate').id})
        self.assertEqual(rec.state, 'invalid')

    def test_07_rule_cost_change_restore_invalidates(self):
        order = self._order(1250)
        rec = self._approve(order.order_line)
        self.cost.write({'amount': 1149})
        self.cost.write({'amount': 1150})
        self.assertEqual(rec.state, 'invalid')
        rec = self._approve(order.order_line)
        self.base_rule.write({'fixed_price': 1349})
        self.assertEqual(rec.state, 'invalid')

    def test_08_single_use_cancel_reset_and_duplicate(self):
        order = self._order(1250)
        rec = self._approve(order.order_line)
        order.action_confirm()
        order._action_cancel()
        order.action_draft()
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_confirm()
        duplicate = order.copy()
        self.assertFalse(duplicate.soles_approval_ids)
        self.assertEqual(rec.state, 'consumed')

    def test_09_forged_approval_and_transition(self):
        order = self._order(1250)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['soles.pricing.approval'].with_user(self.seller).create({'order_id': order.id, 'line_id': order.order_line.id, 'reason': 'fake', 'fingerprint': 'fake', 'requester_id': self.seller.id})
        rec = self._request(order.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint():
            rec.with_user(self.approver).write({'state': 'approved'})
        with self.assertRaises(UserError), self.cr.savepoint():
            order.with_context(soles_skip=True, skip_pricing=True).write({'state': 'sale'})
        with self.assertRaises(UserError), self.cr.savepoint():
            order.write({'state': 'sale', 'order_line': [Command.update(order.order_line.id, {'price_unit': 1250})]})

    def test_10_two_lines_approved_independently(self):
        order = self._order(1250, lines=2)
        a = self._approve(order.order_line[0])
        b = self._approve(order.order_line[1])
        self.assertEqual(a.state, 'approved')
        order.action_confirm()
        self.assertEqual((a | b).mapped('state'), ['consumed', 'consumed'])

    def test_11_priorities_scope_sku_volume_and_dates(self):
        order = self._order()
        rule = self.env['soles.pricing.rule'].create({
            'name': 'Específica', 'scope': 'partner', 'partner_id': self.partner.id,
            'product_ids': [Command.set(self.product.ids)], 'min_qty': 2, 'max_qty': 3,
            'method': 'fixed', 'fixed_price': 1400, 'date_start': fields.Date.today(),
            'date_end': fields.Date.today(), 'currency_id': self.company.currency_id.id})
        self.assertEqual(order.order_line._soles_evaluate()['base_rule_id'], self.base_rule.id)
        order.order_line.write({'product_uom_qty': 2})
        self.assertEqual(order.order_line._soles_evaluate()['base_rule_id'], rule.id)
        rule.write({'sequence': 20})
        self.assertEqual(order.order_line._soles_evaluate()['base_rule_id'], self.base_rule.id)
        rule.write({'sequence': 1, 'date_end': fields.Date.today() - timedelta(days=1), 'date_start': fields.Date.today() - timedelta(days=2)})
        self.assertEqual(order.order_line._soles_evaluate()['base_rule_id'], self.base_rule.id)

    def test_12_user_override_priority(self):
        order = self._order(1250)
        override = self.env['soles.pricing.authority'].create({'name': 'Excepción personal', 'operation': 'discount', 'user_id': self.seller.id, 'max_discount': 8})
        self.assertFalse(order.order_line._soles_evaluate()['needs_approval'])
        override.write({'sequence': 20})
        self.assertTrue(order.order_line._soles_evaluate()['needs_approval'])

    def test_13_margin_floor_requires_explicit_override(self):
        self.company.write({'soles_min_margin': 10})
        order = self._order(1250)
        rec = self._request(order.order_line)
        self.approver_auth.write({'override_floor': False})
        rec = self._request(order.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint():
            rec.with_user(self.approver).action_approve()
        self.approver_auth.write({'override_floor': True})
        self._approve(order.order_line)
        order.action_confirm()

    def test_14_expiry_and_revocation(self):
        order = self._order(1250)
        rec = self._approve(order.order_line)
        rec.sudo().write({'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_confirm()
        rec = self._approve(order.order_line)
        self.approver_auth.write({'active': False})
        self.assertFalse(rec._usable())

    def test_15_security_configuration_and_cost(self):
        order = self._order(1250)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.company.with_user(self.seller).write({'soles_pricing_mode': 'off'})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.partner.with_user(self.seller).write({'soles_segment_id': False})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.cost.with_user(self.seller).read(['amount'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            order.order_line.with_user(self.seller).read(['soles_cost'])
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.product.with_user(self.seller).write({'standard_price': 1})

    def test_16_other_salesperson_isolation(self):
        order = self._order(1250)
        rec = self._request(order.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint():
            rec.with_user(self.other).read(['requested_price'])

    def test_17_multicompany_isolation(self):
        company2 = self.env['res.company'].create({'name': 'Otra compañía pruebas'})
        foreign = self.env['soles.pricing.rule'].create({'name': 'Ajena', 'company_id': company2.id, 'method': 'fixed', 'fixed_price': 1})
        with self.assertRaises(AccessError), self.cr.savepoint():
            foreign.with_user(self.seller).read(['fixed_price'])
        self.assertEqual(self._order().order_line._soles_evaluate()['base_rule_id'], self.base_rule.id)

    def test_18_sequential_math_and_cost_methods(self):
        self.assertEqual(net_price(100, 10, 5, 'additive'), 85)
        self.assertEqual(net_price(100, 10, 5, 'sequential'), 85.5)
        self.assertAlmostEqual(cost_price(80, 20, 'cost_margin'), 100)
        self.assertAlmostEqual(cost_price(80, 20, 'cost_markup'), 96)
        self.base_rule.write({'method': 'cost_margin', 'rate': 20})
        self.company.write({'soles_discount_mode': 'sequential'})
        ev = self._order().order_line._soles_evaluate()
        self.assertAlmostEqual(ev['base'], 1437.5)
        self.assertAlmostEqual(ev['min_price'], 1437.5 * .98 * .97)
        self.assertAlmostEqual(margin(1250, 1150), 8)

    def test_19_native_pricelist_and_uom(self):
        self.base_rule.write({'active': False})
        self.env['product.pricelist.item'].create({'pricelist_id': self.pricelist.id, 'applied_on': '0_product_variant', 'product_id': self.product.id, 'compute_price': 'fixed', 'fixed_price': 1400})
        line = self._order().order_line
        self.assertAlmostEqual(line._soles_evaluate()['base'], 1400)
        line.write({'product_uom': self.env.ref('uom.product_uom_dozen').id})
        ev = line._soles_evaluate()
        self.assertAlmostEqual(ev['base'], 16800)
        self.assertAlmostEqual(ev['cost'], 13800)

    def test_20_tax_included_fixed_price(self):
        tax = self.env['account.tax'].create({'name': 'IVA incluido prueba', 'amount_type': 'percent', 'amount': 16, 'price_include_override': 'tax_included', 'type_tax_use': 'sale', 'company_id': self.company.id})
        order = self._order()
        order.order_line.write({'tax_id': [Command.set(tax.ids)]})
        order.action_soles_reprice()
        self.assertAlmostEqual(order.order_line.price_unit, 1323 * 1.16)
        self.assertAlmostEqual(order.order_line._soles_evaluate()['requested'], 1323)
        self.assertAlmostEqual(order.order_line.price_subtotal, 1323, places=2)

    def test_21_simulator_matches_engine(self):
        sim = self.env['soles.pricing.simulator'].with_user(self.seller).create({
            'partner_id': self.partner.id, 'product_id': self.product.id, 'quantity': 1,
            'uom_id': self.product.uom_id.id, 'pricelist_id': self.pricelist.id,
            'use_requested': True, 'requested_price': 1250})
        sim.action_simulate()
        self.assertAlmostEqual(sim.preferred, 1323)
        self.assertAlmostEqual(sim.min_price, 1282.5)
        self.assertIn('Descuento', sim.result)

    def test_22_missing_cost_and_invalid_inputs(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.cost.copy({'name': 'Superpuesto'})
        self.cost.write({'amount': 0})
        self.product.write({'standard_price': 0})
        order = self._order(1250)
        rec = self._request(order.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint():
            rec.with_user(self.approver).action_approve()
        order.order_line.write({'product_uom_qty': -1})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.action_confirm()

    def test_23_audit_off_and_confirmed_edit(self):
        self.company.write({'soles_pricing_mode': 'audit'})
        order = self._order(1250)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        with self.assertRaises(UserError), self.cr.savepoint():
            order.order_line.write({'price_unit': 1})
        self.company.write({'soles_pricing_mode': 'off'})
        self.assertEqual(self._order(1250).order_line.price_unit, 1250)

    def test_24_delete_line_keeps_history(self):
        order = self._order(1250)
        rec = self._approve(order.order_line)
        order.order_line.unlink()
        self.assertEqual(rec.state, 'invalid')
        self.assertFalse(rec.line_id)

    def test_25_edit_additional_discount_and_native_discount(self):
        order = self._order()
        order.order_line.write({'soles_extra': 3})
        self.assertAlmostEqual(order.order_line.price_unit, 1282.5)
        self.assertAlmostEqual(order.order_line.soles_extra, 3)
        order.order_line.write({'discount': 10})
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_confirm()

    def test_26_currency_conversion(self):
        currency = self.env['res.currency'].create({'name': 'XST', 'symbol': 'T', 'rounding': .01, 'active': True})
        self.env['res.currency.rate'].create({'currency_id': currency.id, 'company_id': self.company.id, 'name': fields.Date.today(), 'rate': 2})
        price_list = self.pricelist.copy({'currency_id': currency.id})
        order = self._order()
        order.write({'pricelist_id': price_list.id})
        order.action_soles_reprice()
        ev = order.order_line._soles_evaluate()
        expected = self.company.currency_id._convert(1350, currency, self.company, fields.Date.today(), round=False)
        self.assertAlmostEqual(ev['base'], expected)
        self.assertAlmostEqual(ev['cost'], expected * 1150 / 1350)
        self.assertAlmostEqual(order.order_line.price_unit, expected * .98)

    def test_27_config_wizard_and_role_separation(self):
        config = self._user('soles_config_test', ['soles_pricing.group_config'])
        policy = self.env['soles.pricing.policy'].with_user(config).create({})
        policy.write({'min_margin': 7})
        policy.action_apply()
        self.assertEqual(self.company.soles_min_margin, 7)
        self.assertFalse(config.has_group('soles_pricing.group_approver'))
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['soles.pricing.policy'].with_user(self.seller).create({})
        self.partner.with_user(config).write({'soles_segment_id': False})
        self.assertFalse(self.partner.soles_segment_id)

    def test_28_brand_and_segment_filters_preview(self):
        order = self._order()
        self.base_rule.write({'brand_id': self.brand.id})
        self.assertEqual(order.order_line._soles_evaluate()['base_rule_id'], self.base_rule.id)
        action = self.base_rule.action_preview_products()
        self.assertIn(self.product, self.env['product.product'].search(action['domain']))
        self.segment.write({'active': False})
        self.assertFalse(order.order_line._soles_evaluate()['base_rule_id'])

    def test_29_rejection_and_forbidden_cost_edit(self):
        order = self._order(1250)
        approval = self._request(order.order_line).with_user(self.approver)
        approval.write({'decision_reason': 'Margen insuficiente para este proyecto'})
        approval.action_reject()
        self.assertEqual(approval.state, 'rejected')
        with self.assertRaises(AccessError), self.cr.savepoint():
            approval.write({'requested_price': 1350})

    def test_30_fiscal_position_and_native_inclusive(self):
        self.base_rule.write({'active': False})
        tax = self.env['account.tax'].create({'name': 'IVA incluido lista', 'amount_type': 'percent', 'amount': 16, 'price_include_override': 'tax_included', 'type_tax_use': 'sale', 'company_id': self.company.id})
        self.product.write({'list_price': 1740, 'taxes_id': [Command.set(tax.ids)]})
        order = self._order()
        order.order_line.write({'tax_id': [Command.set(tax.ids)]})
        order.action_soles_reprice()
        self.assertAlmostEqual(order.order_line._soles_evaluate()['base'], 1500)
        self.assertAlmostEqual(order.order_line._soles_evaluate()['requested'], 1470)
        position = self.env['account.fiscal.position'].create({'name': 'Exento pruebas', 'company_id': self.company.id, 'tax_ids': [Command.create({'tax_src_id': tax.id})]})
        order.write({'fiscal_position_id': position.id})
        order.order_line.write({'tax_id': [Command.clear()]})
        order.action_soles_reprice()
        self.assertAlmostEqual(order.order_line.price_unit, 1470)

    def test_31_native_downpayment_and_invoice(self):
        receivable = self.env['account.account'].create({'name': 'Receivable test', 'code': 'SP1100', 'account_type': 'asset_receivable', 'reconcile': True, 'company_ids': [Command.set(self.company.ids)]})
        payable = self.env['account.account'].create({'name': 'Payable test', 'code': 'SP2100', 'account_type': 'liability_payable', 'reconcile': True, 'company_ids': [Command.set(self.company.ids)]})
        income = self.env['account.account'].create({'name': 'Income test', 'code': 'SP4100', 'account_type': 'income', 'company_ids': [Command.set(self.company.ids)]})
        self.env['account.journal'].create({'name': 'Soles invoice test', 'code': 'SPT', 'type': 'sale', 'company_id': self.company.id, 'default_account_id': income.id})
        self.partner.write({'property_account_receivable_id': receivable.id, 'property_account_payable_id': payable.id})
        self.product.write({'property_account_income_id': income.id, 'invoice_policy': 'order'})
        order = self._order(1282.5)
        order.action_confirm()
        wizard = self.env['sale.advance.payment.inv'].create({'sale_order_ids': [Command.set(order.ids)], 'advance_payment_method': 'percentage', 'amount': 20})
        invoice = wizard._create_invoices(order)
        self.assertAlmostEqual(invoice.amount_untaxed, 256.5)
        deposits = order.order_line.filtered(lambda l: l.is_downpayment and not l.display_type)
        self.assertTrue(deposits.soles_native_downpayment)
        # Public JSON contexts and down-payment flags cannot exempt a sales line.
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env['sale.order.line'].with_user(self.seller).with_context(_soles_native_downpayment=True).create({'order_id': order.id, 'is_downpayment': True, 'product_uom_qty': 0, 'price_unit': 1, 'name': 'Falso anticipo'})
        with self.assertRaises(AccessError), self.cr.savepoint():
            order.order_line[:1].write({'soles_native_downpayment': True})

    def test_32_salesperson_cannot_backdate_or_modify_native(self):
        order = self._order(1250)
        with self.assertRaises(AccessError), self.cr.savepoint():
            order.write({'soles_pricing_date': fields.Date.today() - timedelta(days=1)})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['product.pricelist'].with_user(self.seller).create({'name': 'Lista no autorizada'})
        config = self._user('soles_config_product', ['soles_pricing.group_config'])
        self.product.with_user(config).write({'soles_brand_id': False})

    def test_33_audit_does_not_block_unsupported_quantities(self):
        self.company.write({'soles_pricing_mode': 'audit'})
        order = self._order(1250)
        order.order_line.write({'product_uom_qty': -1})
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
