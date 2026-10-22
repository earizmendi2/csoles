from datetime import timedelta
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged, Form
from .common import build_fixture, publish, revise, order, request, approve


@tagged('post_install', '-at_install')
class TestSpecification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.f = build_fixture(cls.env)

    def test_01_sequential_case(self):
        o = order(self.f)
        line = o.order_line
        self.assertAlmostEqual(line.price_unit, 1323)
        self.assertAlmostEqual(line._soles_evaluate()['min_price'], 1283.31)
        line.write({'price_unit': 1250})
        ev = line._soles_evaluate()
        self.assertAlmostEqual(ev['extra'], (1 - 1250 / 1323) * 100)
        self.assertAlmostEqual(ev['margin'], 8)
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()
        a = approve(self.f, line)
        o.action_confirm()
        self.assertEqual(a.state, 'consumed')
        self.assertEqual(a.consumption_count, 1)

    def test_02_authorized_discount(self):
        o = order(self.f, 1283.31)
        o.action_confirm()
        self.assertEqual(o.state, 'sale')
        self.assertFalse(o.soles_approval_ids)

    def test_03_same_customer_price_for_different_sellers(self):
        self.assertAlmostEqual(order(self.f).order_line.price_unit, order(self.f, user=self.f.manager).order_line.price_unit)
        self.assertFalse(self.f.manager.has_group('soles_pricing.group_approver'))

    def test_04_user_authority_override(self):
        self.env['soles.pricing.authority'].create({'name': 'Excepción personal', 'user_id': self.f.seller.id, 'max_discount': 6})
        self.assertFalse(order(self.f, 1250).order_line._soles_evaluate()['needs_approval'])

    def test_05_published_documents_are_immutable(self):
        with self.assertRaises(UserError), self.cr.savepoint(): self.f.base_rule.write({'fixed_price': 1})
        with self.assertRaises(AccessError), self.cr.savepoint(): self.f.base_rule.with_context(_soles_publication=True).write({'state': 'draft'})
        with self.assertRaises(AccessError), self.cr.savepoint(): self.f.base_rule.version_id.write({'payload': {}})

    def test_06_publish_permissions_separate_from_editing(self):
        rule = self.env['soles.pricing.rule'].with_user(self.f.editor).create({'name': 'Borrador nuevo', 'method': 'fixed', 'fixed_price': 1400, 'justification': 'Propuesta'})
        rule.action_submit()
        with self.assertRaises(AccessError), self.cr.savepoint(): rule.action_publish()
        rule.with_user(self.f.publisher).action_publish()
        self.assertEqual(rule.state, 'published')
        self.assertEqual(rule.publisher_id, self.f.publisher)

    def test_07_drafts_not_used_and_can_be_previewed(self):
        draft = self.env['soles.pricing.rule'].create({'name': 'Propuesta cliente', 'scope': 'partner', 'partner_id': self.f.partner.id, 'method': 'fixed', 'fixed_price': 1400})
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1323)
        sim = self.env['soles.pricing.simulator'].with_user(self.f.editor).create({'partner_id': self.f.partner.id, 'product_id': self.f.product.id,
            'quantity': 1, 'uom_id': self.f.product.uom_id.id, 'pricelist_id': self.f.pricelist.id, 'preview_rule_id': draft.id})
        sim.action_simulate()
        self.assertAlmostEqual(sim.preferred, 1372)
        self.assertEqual(draft.state, 'draft')

    def test_08_revisions_preserve_old_quotes(self):
        o = order(self.f)
        original = o.order_line.sudo().soles_valuation_json
        new = revise(self.f.base_rule, fixed_price=1500)
        self.assertEqual(self.f.base_rule.state, 'inactive')
        self.assertEqual(new.revision, 2)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['preferred'], 1323)
        self.assertEqual(o.order_line.sudo().soles_valuation_json, original)
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1470)
        o.action_soles_reprice()
        self.assertAlmostEqual(o.order_line.price_unit, 1470)
        self.assertEqual(o.order_line.soles_base_version_id, new.version_id)

    def test_09_avco_cannot_change_commercial_cost(self):
        o = order(self.f)
        self.f.product.write({'standard_price': 100})
        self.assertAlmostEqual(o.order_line._soles_evaluate()['cost'], 1150)
        self.assertEqual(o.order_line.soles_cost_version_id, self.f.cost.version_id)

    def test_10_published_cost_revalidation_does_not_change_price(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        revise(self.f.cost, amount=1200)
        self.assertEqual(a.state, 'invalid')
        self.assertAlmostEqual(o.order_line.price_unit, 1250)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['cost'], 1200)

    def test_11_draft_edits_do_not_invalidate_approval(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        draft = self.env['soles.pricing.rule'].create({'name': 'Sin publicar', 'method': 'fixed', 'fixed_price': 500})
        draft.write({'fixed_price': 501})
        self.assertEqual(a.state, 'approved')
        self.assertTrue(a.sudo()._usable())

    def test_12_cost_overlap_is_checked_at_publication(self):
        duplicate = self.f.cost.copy({'name': 'Otra fuente'})
        self.assertEqual(duplicate.state, 'draft')
        with self.assertRaises(ValidationError), self.cr.savepoint(): publish(duplicate)

    def test_13_cost_source_required(self):
        draft = self.f.cost.copy({'source_reference': False})
        with self.assertRaises(ValidationError), self.cr.savepoint(): publish(draft)

    def test_14_missing_commercial_cost_blocks_even_with_avco(self):
        self.f.cost.action_deactivate()
        self.f.product.write({'standard_price': 999})
        o = order(self.f)
        self.assertTrue(o.order_line._soles_evaluate()['hard_reasons'])
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_15_commercial_fx(self):
        currency = self.env['res.currency'].create({'name': 'QFX', 'symbol': 'Q', 'rounding': .01})
        fx = publish(self.env['soles.pricing.fx'].create({'name': 'Cambio QA', 'currency_id': currency.id,
            'rate': 2, 'source_reference': 'Boletín QA', 'date_start': fields.Date.today()}))
        pl = self.f.pricelist.copy({'currency_id': currency.id})
        o = order(self.f, pricelist_id=pl.id)
        self.assertAlmostEqual(o.order_line.price_unit, 661.5)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['cost'], 575)
        self.assertTrue(fx.version_id)

    def test_16_missing_fx_fails_closed(self):
        currency = self.env['res.currency'].create({'name': 'QNF', 'symbol': 'N', 'rounding': .01})
        pl = self.f.pricelist.copy({'currency_id': currency.id})
        with self.assertRaises(ValidationError), self.cr.savepoint(): order(self.f, pricelist_id=pl.id)

    def test_17_quote_monetary_limit_cannot_be_split(self):
        self.f.seller_auth.write({'limit_discount_amount': True, 'max_discount_amount': 50})
        o = order(self.f, 1290, lines=2)
        ev = o.order_line[0]._soles_evaluate()
        self.assertAlmostEqual(ev['quote_discount_company'], 66)
        self.assertTrue(ev['needs_approval'])
        a = approve(self.f, o.order_line[0])
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()
        self.assertEqual(a.state, 'approved')
        b = approve(self.f, o.order_line[1])
        o.action_confirm()
        self.assertEqual((a | b).mapped('consumption_count'), [1, 1])

    def test_18_operation_amount_limit(self):
        self.f.seller_auth.write({'limit_order_amount': True, 'max_order_amount': 1000})
        self.assertTrue(order(self.f).order_line._soles_evaluate()['needs_approval'])
        self.f.approver_auth.write({'limit_order_amount': True, 'max_order_amount': 1000})
        a = request(order(self.f).order_line)
        self.assertFalse(a.reviewer_ids)

    def test_19_manufacturer_hard_floor(self):
        publish(self.env['soles.pricing.limit'].create({'name': 'MAP QA', 'family_id': self.f.family.id,
            'currency_id': self.f.company.currency_id.id, 'minimum_price': 1400}))
        o = order(self.f)
        self.assertTrue(o.order_line._soles_evaluate()['hard_reasons'])
        a = request(o.order_line)
        self.assertFalse(a.reviewer_ids)
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_20_manufacturer_override_is_independent(self):
        publish(self.env['soles.pricing.limit'].create({'name': 'Excepción MAP QA', 'family_id': self.f.family.id,
            'currency_id': self.f.company.currency_id.id, 'minimum_price': 1400, 'overridable': True}))
        o = order(self.f)
        self.f.approver_auth.write({'override_manufacturer': False})
        self.assertFalse(request(o.order_line).reviewer_ids)
        self.f.approver_auth.write({'override_manufacturer': True})
        approve(self.f, o.order_line)
        o.action_confirm()
        self.assertEqual(o.state, 'sale')

    def test_21_family_exception_floor_cannot_be_overridden(self):
        self.f.family.write({'min_margin': 12, 'exception_margin': 9})
        a = request(order(self.f, 1250).order_line)
        self.assertFalse(a.reviewer_ids)

    def test_22_unclassified_products_block(self):
        self.f.product.write({'soles_product_policy_id': False})
        o = order(self.f)
        self.assertTrue(o.order_line._soles_evaluate()['hard_reasons'])
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_23_manual_quote_without_list_reference(self):
        self.f.base_rule.action_deactivate()
        self.f.benefit.action_deactivate()
        self.f.product.write({'list_price': 0, 'soles_product_policy_id': self.env.ref('soles_pricing.classification_quote').id})
        o = order(self.f, 1250)
        ev = o.order_line._soles_evaluate()
        self.assertFalse(ev['hard_reasons'])
        self.assertTrue(ev['manual_approval'])
        approve(self.f, o.order_line)
        o.action_confirm()
        self.assertEqual(o.state, 'sale')

    def test_24_quantity_changes_recapture_valuation(self):
        volume = publish(self.env['soles.pricing.rule'].create({'name': 'Volumen QA', 'scope': 'partner', 'partner_id': self.f.partner.id,
            'family_id': self.f.family.id, 'min_qty': 2, 'method': 'fixed', 'fixed_price': 1300}))
        o = order(self.f)
        o.order_line.write({'product_uom_qty': 2})
        self.assertEqual(o.order_line._soles_evaluate()['base_rule_id'], volume.id)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['preferred'], 1274)

    def test_25_change_restore_invalidates(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        o.order_line.write({'price_unit': 1249})
        o.order_line.write({'price_unit': 1250})
        self.assertEqual(a.state, 'invalid')
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_26_one_use_and_cancellation(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        o.action_confirm()
        o._action_cancel()
        o.action_draft()
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()
        self.assertEqual(a.consumption_count, 1)
        self.assertFalse(o.copy().soles_approval_ids)

    def test_27_api_cannot_forge_controls(self):
        o = order(self.f, 1250)
        with self.assertRaises(AccessError), self.cr.savepoint(): o.order_line.write({'soles_valuation_json': {}})
        with self.assertRaises(UserError), self.cr.savepoint(): o.with_context(skip_pricing=True).write({'state': 'sale'})
        a = request(o.order_line)
        with self.assertRaises(AccessError), self.cr.savepoint(): a.with_user(self.f.approver).write({'state': 'approved'})
        with self.assertRaises(AccessError), self.cr.savepoint(): self.env['soles.pricing.approval'].with_user(self.f.seller).create({'name': 'FAKE'})

    def test_28_costs_and_versions_are_confidential(self):
        line = order(self.f).order_line
        with self.assertRaises(AccessError), self.cr.savepoint(): line.read(['soles_valuation_json'])
        with self.assertRaises(AccessError), self.cr.savepoint(): self.f.cost.with_user(self.f.seller).read(['amount'])
        with self.assertRaises(AccessError), self.cr.savepoint(): self.f.cost.version_id.with_user(self.f.seller).read(['payload'])
        result = self.env['soles.pricing.engine'].with_user(self.f.seller).get_customer_price(self.f.partner.id, self.f.product.id, pricelist_id=self.f.pricelist.id)
        self.assertNotIn('cost', result)
        self.assertAlmostEqual(result['preferred'], 1323)

    def test_29_multicompany(self):
        company = self.env['res.company'].create({'name': 'Otra empresa QA'})
        foreign = self.env['soles.pricing.family'].with_company(company).create({'name': 'Familia ajena', 'company_id': company.id})
        with self.assertRaises(AccessError), self.cr.savepoint(): foreign.with_user(self.f.seller).read(['name'])
        with self.assertRaises(ValidationError), self.cr.savepoint(): self.f.product.write({'soles_family_id': foreign.id})

    def test_30_expiry(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        a.sudo().write({'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        self.env['soles.pricing.approval']._cron_expire()
        self.assertEqual(a.state, 'expired')
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_31_reject_and_cancel_requests(self):
        o = order(self.f, 1250)
        a = request(o.order_line)
        reviewer = a.with_user(self.f.approver)
        reviewer.write({'decision_reason': 'Rechazado por política'})
        reviewer.action_reject()
        self.assertEqual(a.state, 'rejected')
        b = request(o.order_line)
        b.action_cancel()
        self.assertEqual(b.state, 'cancelled')

    def test_32_activity_routing_and_resolution(self):
        o = order(self.f, 1250)
        a = request(o.order_line)
        self.assertEqual(a.reviewer_ids, self.f.approver)
        self.assertEqual(a.sudo().activity_ids.user_id, self.f.approver)
        o.order_line.write({'product_uom_qty': 2})
        self.assertEqual(a.state, 'invalid')
        self.assertFalse(a.sudo().activity_ids)

    def test_33_route_escalates_only_to_sufficient_authority(self):
        special = self.f.new_user('especial', ['soles_pricing.group_approver'])
        self.f.approver_auth.write({'max_discount': 4})
        self.env['soles.pricing.authority'].create({'name': 'Dirección QA', 'operation': 'approve', 'user_id': special.id, 'max_discount': 20, 'override_floor': True})
        route = self.env['soles.pricing.route'].create({'name': 'Escalamiento QA', 'sequence': 20, 'reviewer_ids': [Command.set(special.ids)]})
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line, user=special)
        self.assertEqual(a.route_id, route)
        self.assertEqual(a.approver_id, special)

    def test_34_no_self_approval(self):
        self.f.route.write({'reviewer_ids': [Command.set(self.f.approver.ids)]})
        o = order(self.f, 1250, user=self.f.approver)
        self.assertFalse(request(o.order_line).reviewer_ids)

    def test_35_financial_roles_are_separate(self):
        with self.assertRaises(AccessError), self.cr.savepoint(): self.f.cost.with_user(self.f.editor).copy()
        self.assertFalse(self.f.publisher.has_group('soles_pricing.group_approver'))
        self.assertFalse(self.f.editor.has_group('soles_pricing.group_publisher'))

    def test_36_benefits_need_explicit_policy(self):
        self.f.company.write({'soles_allow_benefit': False})
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1350)
        self.f.family.write({'benefit_policy': 'allow'})
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1323)

    def test_37_family_is_independent_of_inventory_category(self):
        category = self.env['product.category'].create({'name': 'Categoría contable QA'})
        self.f.product.write({'categ_id': category.id})
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1323)

    def test_38_priority_matrix_is_editable(self):
        general = publish(self.env['soles.pricing.rule'].create({'name': 'General SKU QA', 'product_ids': [Command.set(self.f.product.ids)], 'method': 'fixed', 'fixed_price': 1400}))
        self.assertEqual(order(self.f).order_line._soles_evaluate()['base_rule_id'], self.f.base_rule.id)
        self.env['soles.pricing.precedence'].search([('operation', '=', 'rule'), ('scope', '=', 'general')]).write({'sequence': 1})
        self.assertEqual(order(self.f).order_line._soles_evaluate()['base_rule_id'], general.id)

    def test_39_native_pricelist_uses_commercial_fx(self):
        self.f.base_rule.action_deactivate()
        currency = self.env['res.currency'].create({'name': 'QNP', 'symbol': 'P', 'rounding': .01})
        publish(self.env['soles.pricing.fx'].create({'name': 'FX nativo QA', 'currency_id': currency.id, 'rate': 2, 'source_reference': 'QA'}))
        pl = self.f.pricelist.copy({'currency_id': currency.id})
        self.assertAlmostEqual(order(self.f, pricelist_id=pl.id).order_line.price_unit, 735)

    def test_40_uom_and_tax_included(self):
        tax = self.env['account.tax'].create({'name': 'IVA QA', 'amount_type': 'percent', 'amount': 16, 'price_include_override': 'tax_included', 'type_tax_use': 'sale', 'company_id': self.f.company.id})
        o = order(self.f)
        o.order_line.write({'tax_id': [Command.set(tax.ids)], 'product_uom': self.env.ref('uom.product_uom_dozen').id})
        o.action_soles_reprice()
        ev = o.order_line._soles_evaluate()
        self.assertAlmostEqual(ev['preferred'], 1323 * 12)
        self.assertAlmostEqual(ev['requested'], 1323 * 12)
        self.assertAlmostEqual(ev['cost'], 1150 * 12)

    def test_41_cost_margin_method(self):
        revise(self.f.base_rule, method='cost_margin', rate=20)
        self.assertAlmostEqual(order(self.f).order_line._soles_evaluate()['base'], 1437.5)

    def test_42_publication_history_is_immutable(self):
        revision = revise(self.f.base_rule, fixed_price=1400)
        self.assertEqual(revision.version_id.payload['fixed_price'], 1400)
        self.assertEqual(self.f.base_rule.version_id.payload['fixed_price'], 1350)
        with self.assertRaises(AccessError), self.cr.savepoint(): revision.version_id.unlink()
        audit = self.env['soles.pricing.audit'].search([('model_name', '=', 'soles.pricing.rule'), ('record_id', '=', revision.id)], limit=1)
        self.assertTrue(audit)
        with self.assertRaises(AccessError), self.cr.savepoint(): audit.write({'operation': 'FAKE'})

    def test_43_internal_service_requires_sales_access(self):
        user = self.f.new_user('interno', ['base.group_user'])
        with self.assertRaises(AccessError), self.cr.savepoint(): self.env['soles.pricing.engine'].with_user(user).get_customer_price(self.f.partner.id, self.f.product.id)

    def test_44_order_inputs_invalidate_and_revalue(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        partner = self.env['res.partner'].create({'name': 'Otro cliente', 'soles_segment_id': self.f.segment.id})
        o.write({'partner_id': partner.id})
        self.assertEqual(a.state, 'invalid')
        self.assertAlmostEqual(o.order_line._soles_evaluate()['preferred'], 1350)

    def test_45_rule_dates_and_currency_scope(self):
        publish(self.env['soles.pricing.rule'].create({'name': 'Vencida QA', 'scope': 'partner', 'partner_id': self.f.partner.id, 'method': 'fixed', 'fixed_price': 1,
            'date_start': fields.Date.today() - timedelta(days=3), 'date_end': fields.Date.today() - timedelta(days=1)}))
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1323)
        with self.assertRaises(AccessError), self.cr.savepoint(): order(self.f).write({'soles_pricing_date': fields.Date.today() - timedelta(days=1)})

    def test_46_simulator_and_form(self):
        sim = self.env['soles.pricing.simulator'].with_user(self.f.seller).create({'partner_id': self.f.partner.id, 'product_id': self.f.product.id,
            'quantity': 1, 'uom_id': self.f.product.uom_id.id, 'pricelist_id': self.f.pricelist.id, 'use_requested': True, 'requested_price': 1250})
        sim.action_simulate()
        self.assertAlmostEqual(sim.preferred, 1323)
        self.assertAlmostEqual(sim.min_price, 1283.31)
        form = Form(self.env['sale.order'].with_user(self.f.seller))
        form.partner_id = self.f.partner
        with form.order_line.new() as line:
            line.product_id = self.f.product
        quotation = form.save()
        self.assertAlmostEqual(quotation.order_line.price_unit, 1323)

    def test_47_audit_and_off_modes(self):
        self.f.company.write({'soles_pricing_mode': 'audit'})
        o = order(self.f, 1250)
        o.action_confirm()
        self.assertEqual(o.state, 'sale')
        self.f.company.write({'soles_pricing_mode': 'off'})
        self.assertAlmostEqual(order(self.f, 1250).order_line.price_unit, 1250)

    def test_48_delete_line_keeps_history(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        o.order_line.unlink()
        self.assertEqual(a.state, 'invalid')
        self.assertFalse(a.line_id)

    def test_49_legacy_mode_setting_cannot_change_vendor_formula(self):
        self.f.company.write({'soles_discount_mode': 'additive'})
        self.assertAlmostEqual(order(self.f).order_line._soles_evaluate()['min_price'], 1283.31)

    def test_50_additional_discount_field(self):
        o = order(self.f)
        o.order_line.write({'soles_extra': 3})
        self.assertAlmostEqual(o.order_line.price_unit, 1283.31)

    def _accounting(self):
        company = self.f.company
        receivable = self.env['account.account'].create({'name': 'Receivable QA', 'code': 'SP1100', 'account_type': 'asset_receivable', 'reconcile': True, 'company_ids': [Command.set(company.ids)]})
        payable = self.env['account.account'].create({'name': 'Payable QA', 'code': 'SP2100', 'account_type': 'liability_payable', 'reconcile': True, 'company_ids': [Command.set(company.ids)]})
        income = self.env['account.account'].create({'name': 'Income QA', 'code': 'SP4100', 'account_type': 'income', 'company_ids': [Command.set(company.ids)]})
        self.env['account.journal'].create({'name': 'Soles QA', 'code': 'SPT', 'type': 'sale', 'company_id': company.id, 'default_account_id': income.id})
        self.f.partner.write({'property_account_receivable_id': receivable.id, 'property_account_payable_id': payable.id})
        self.f.product.write({'property_account_income_id': income.id})

    def test_51_stock_delivery_and_invoice(self):
        self._accounting()
        self.f.product.write({'is_storable': True, 'invoice_policy': 'delivery'})
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.f.company.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(self.f.product, warehouse.lot_stock_id, 10)
        o = order(self.f, 1250).sudo()
        a = approve(self.f, o.order_line)
        o.action_confirm()
        self.assertEqual(a.consumption_count, 1)
        picking = o.picking_ids
        picking.action_assign()
        self.assertEqual(picking.state, 'assigned')
        picking.move_ids.write({'quantity': 1, 'picked': True})
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertAlmostEqual(o.order_line.qty_delivered, 1)
        invoice = o._create_invoices()
        self.assertAlmostEqual(invoice.amount_untaxed, 1250)
        self.assertAlmostEqual(invoice.invoice_line_ids.price_unit, 1250)
        self.assertEqual(a.consumption_count, 1)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['cost'], 1150)

    def test_52_native_advance_and_false_advance(self):
        self._accounting()
        self.f.product.write({'invoice_policy': 'order'})
        o = order(self.f, 1283.31).sudo()
        o.action_confirm()
        wizard = self.env['sale.advance.payment.inv'].create({'sale_order_ids': [Command.set(o.ids)], 'advance_payment_method': 'percentage', 'amount': 20})
        invoice = wizard._create_invoices(o)
        self.assertAlmostEqual(invoice.amount_untaxed, 256.66)
        self.assertTrue(o.order_line.filtered(lambda l: l.is_downpayment and not l.display_type).soles_native_downpayment)
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env['sale.order.line'].with_user(self.f.seller).with_context(_soles_native_downpayment=True).create({'order_id': o.id, 'is_downpayment': True, 'product_uom_qty': 0, 'price_unit': 1, 'name': 'Falso anticipo'})

    def test_53_approval_does_not_transfer_to_another_line(self):
        o = order(self.f, 1250, lines=2)
        a = approve(self.f, o.order_line[0])
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()
        b = approve(self.f, o.order_line[1])
        o.action_confirm()
        self.assertEqual(a.consumption_count, 1)
        self.assertEqual(b.consumption_count, 1)

    def test_54_native_brand_mapping(self):
        native = self.env['ir.model.fields'].search([('model', '=', 'product.template'), ('name', '=', 'categ_id')])
        self.f.company.write({'soles_brand_field_id': native.id})
        self.f.brand.write({'native_model': 'product.category', 'native_id': self.f.product.categ_id.id})
        self.f.product.write({'soles_brand_id': False})
        publish(self.env['soles.pricing.rule'].create({'name': 'Marca existente QA', 'scope': 'partner', 'partner_id': self.f.partner.id, 'brand_id': self.f.brand.id, 'method': 'fixed', 'fixed_price': 1400}))
        self.assertAlmostEqual(order(self.f).order_line.price_unit, 1372)

    def test_55_zero_and_one_are_not_automatically_valid(self):
        self.f.base_rule.action_deactivate()
        self.f.product_policy.write({'minimum_reference': 1})
        self.f.product.write({'list_price': 1})
        o = order(self.f)
        self.assertTrue(o.order_line._soles_evaluate()['hard_reasons'])
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_56_operating_floor_needs_separate_override(self):
        self.f.family.write({'min_margin': 10, 'exception_margin': 5})
        self.f.approver_auth.write({'override_floor': False})
        o = order(self.f, 1250)
        a = request(o.order_line)
        self.assertFalse(a.reviewer_ids)
        self.f.approver_auth.write({'override_floor': True})
        a = approve(self.f, o.order_line)
        o.action_confirm()
        self.assertEqual(a.state, 'consumed')

    def test_57_authority_revocation_invalidates(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        self.f.approver.write({'active': False})
        self.assertFalse(a._usable())
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_58_volume_specific_rule(self):
        rule = publish(self.env['soles.pricing.rule'].create({'name': 'Volumen QA', 'scope': 'partner', 'partner_id': self.f.partner.id,
            'product_ids': [Command.set(self.f.product.ids)], 'min_qty': 10, 'method': 'fixed', 'fixed_price': 1300}))
        o = order(self.f)
        o.order_line.write({'product_uom_qty': 10})
        o.action_soles_reprice()
        self.assertAlmostEqual(o.order_line.price_unit, 1274)
        self.assertEqual(o.order_line.soles_base_rule_id, rule)

    def test_59_approval_company_history_immutable(self):
        o = order(self.f, 1250)
        a = approve(self.f, o.order_line)
        other = self.env['res.company'].create({'name': 'Otra empresa QA'})
        with self.assertRaises(UserError), self.cr.savepoint(): o.sudo().write({'company_id': other.id})
        self.assertEqual(a.company_id, self.f.company)
        self.assertEqual(a.currency_id, self.f.pricelist.currency_id)

    def test_60_current_seller_limit_over_frozen_price(self):
        o = order(self.f, 1283.31)
        self.f.seller_auth.write({'max_discount': 1})
        self.assertAlmostEqual(o.order_line.price_unit, 1283.31)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['preferred'], 1323)
        self.assertTrue(o.order_line._soles_evaluate()['needs_approval'])

    def test_61_quality_floor_is_per_base_unit(self):
        self.f.base_rule.action_deactivate()
        self.f.product_policy.write({'minimum_reference': 1})
        self.f.product.write({'list_price': 1})
        o = order(self.f)
        o.order_line.write({'product_uom': self.env.ref('uom.product_uom_dozen').id})
        o.action_soles_reprice()
        self.assertTrue(o.order_line._soles_evaluate()['hard_reasons'])
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()

    def test_62_audit_before_after_and_actor(self):
        route = self.f.route.with_user(self.f.editor)
        route.write({'name': 'Ruta revisada QA'})
        audit = self.env['soles.pricing.audit'].search([('model_name', '=', route._name), ('record_id', '=', route.id), ('operation', '=', 'write')], order='id desc', limit=1)
        self.assertEqual(audit.changes['before']['name'], 'Gerencia QA')
        self.assertEqual(audit.changes['after']['name'], 'Ruta revisada QA')
        self.assertEqual(audit.actor_id, self.f.editor)

    def test_63_simulator_uses_same_eligible_route(self):
        sim = self.env['soles.pricing.simulator'].with_user(self.f.seller).create({'partner_id': self.f.partner.id, 'product_id': self.f.product.id,
            'quantity': 1, 'uom_id': self.f.product.uom_id.id, 'pricelist_id': self.f.pricelist.id, 'use_requested': True, 'requested_price': 1250})
        sim.action_simulate()
        a = request(order(self.f, 1250).order_line)
        self.assertIn(a.route_id.name, sim.result)
        self.assertIn(self.f.approver.name, sim.result)

    def test_64_native_inclusive_tax_and_exemption(self):
        self.f.base_rule.action_deactivate()
        tax = self.env['account.tax'].create({'name': 'IVA incluido QA', 'amount_type': 'percent', 'amount': 16, 'price_include_override': 'tax_included', 'type_tax_use': 'sale', 'company_id': self.f.company.id})
        self.f.product.write({'list_price': 1740, 'taxes_id': [Command.set(tax.ids)]})
        o = order(self.f)
        o.order_line.write({'tax_id': [Command.set(tax.ids)]})
        o.action_soles_reprice()
        self.assertAlmostEqual(o.order_line._soles_evaluate()['preferred'], 1470)
        self.assertAlmostEqual(o.order_line.price_unit, 1705.2)
        position = self.env['account.fiscal.position'].create({'name': 'Exento QA', 'company_id': self.f.company.id, 'tax_ids': [Command.create({'tax_src_id': tax.id})]})
        o.write({'fiscal_position_id': position.id})
        o.order_line.write({'tax_id': [Command.clear()]})
        o.action_soles_reprice()
        self.assertAlmostEqual(o.order_line.price_unit, 1470)

    def test_65_quotes_created_in_native_mode_require_explicit_valuation(self):
        self.f.company.write({'soles_pricing_mode': 'off'})
        o = order(self.f, 1250)
        self.assertFalse(o.order_line.sudo().soles_valuation_json)
        self.f.company.write({'soles_pricing_mode': 'enforce'})
        with self.assertRaises(UserError), self.cr.savepoint(): o.action_confirm()
        o.action_soles_reprice()
        self.assertAlmostEqual(o.order_line.price_unit, 1323)
        o.action_confirm()
        self.assertEqual(o.state, 'sale')

    def test_66_displayed_minimum_includes_margin_and_manufacturer(self):
        self.f.family.write({'min_margin': 20})
        o = order(self.f)
        self.assertAlmostEqual(o.order_line._soles_evaluate()['min_price'], 1437.5)
        publish(self.env['soles.pricing.limit'].create({'name': 'Piso QA', 'minimum_price': 1450}))
        self.assertAlmostEqual(o.order_line._soles_evaluate()['min_price'], 1450)
        self.assertTrue(o.order_line._soles_evaluate()['needs_approval'])

    def test_67_salesperson_assignment_cannot_borrow_a_faculty(self):
        self.env['soles.pricing.authority'].create({'name': 'Especial QA', 'operation': 'discount', 'user_id': self.f.manager.id, 'max_discount': 10})
        o = order(self.f, 1250, user=self.f.approver, user_id=self.f.manager.id)
        self.assertEqual(o.order_line.soles_negotiator_id, self.f.approver)
        self.assertTrue(o.order_line._soles_evaluate()['needs_approval'])
        with self.assertRaises(UserError), self.cr.savepoint(): o.sudo().action_confirm()
        o.with_user(self.f.manager).order_line.write({'price_unit': 1250})
        self.assertEqual(o.order_line.soles_negotiator_id, self.f.manager)
        self.assertFalse(o.order_line._soles_evaluate()['needs_approval'])
        o.with_user(self.f.manager).action_confirm()

    def test_68_negotiator_identity_cannot_be_forged(self):
        o = order(self.f)
        with self.assertRaises(AccessError), self.cr.savepoint(): o.order_line.write({'soles_negotiator_id': self.f.manager.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['sale.order.line'].with_user(self.f.seller).create({'order_id': o.id, 'product_id': self.f.product.id, 'soles_negotiator_id': self.f.manager.id})

    def test_69_negotiator_cannot_approve_own_discount_by_reassigning(self):
        o = order(self.f)
        o.with_user(self.f.approver).order_line.write({'price_unit': 1250})
        self.assertEqual(o.order_line.soles_negotiator_id, self.f.approver)
        a = request(o.order_line)
        self.assertFalse(a.reviewer_ids)
        with self.assertRaises(AccessError), self.cr.savepoint(): a.with_user(self.f.approver).action_approve()

    def test_70_native_and_audit_modes_remain_usable_without_commercial_fx(self):
        currency = self.env['res.currency'].create({'name': 'QNO', 'symbol': 'O', 'rounding': .01})
        pl = self.f.pricelist.copy({'currency_id': currency.id})
        for mode in ('off', 'audit'):
            self.f.company.write({'soles_pricing_mode': mode})
            o = order(self.f, 1250, pricelist_id=pl.id)
            self.assertTrue(o.order_line.soles_explanation)
            o.action_confirm()
            self.assertEqual(o.state, 'sale')
