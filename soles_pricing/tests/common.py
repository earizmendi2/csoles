from types import SimpleNamespace
from datetime import timedelta
import uuid
from odoo import Command, fields


def publish(record):
    record.write({'justification': 'Condiciones de prueba revisadas'})
    record.action_submit()
    record.action_publish()
    return record


def revise(record, **values):
    action = record.action_new_revision()
    new = record.env[record._name].browse(action['res_id'])
    new.write(values)
    return publish(new)


def build_fixture(env):
    f = SimpleNamespace(env=env, company=env.company)
    f.company.write({'soles_pricing_mode': 'off'})
    for model in ('soles.pricing.rule', 'soles.pricing.cost', 'soles.pricing.fx', 'soles.pricing.limit'):
        records = env[model].with_context(active_test=False).search([('company_id', '=', f.company.id), ('state', '=', 'published')])
        if records:
            records.action_deactivate()
    for model in ('soles.pricing.authority', 'soles.pricing.route'):
        env[model].search([('company_id', '=', f.company.id)]).write({'active': False})
    def user(label, groups):
        login = 'sp_test_' + label + '_' + uuid.uuid4().hex[:10]
        return env['res.users'].with_context(no_reset_password=True).create({
            'name': label, 'login': login, 'email': login + '@example.invalid', 'company_id': f.company.id,
            'company_ids': [Command.set(f.company.ids)], 'groups_id': [Command.set([env.ref(g).id for g in groups])]})
    f.new_user = user
    f.seller = user('vendedor', ['soles_pricing.group_seller'])
    f.other = user('otro_vendedor', ['soles_pricing.group_seller'])
    f.manager = user('gerente', ['soles_pricing.group_manager'])
    f.approver = user('aprobador', ['soles_pricing.group_approver'])
    f.editor = user('editor', ['soles_pricing.group_config'])
    f.publisher = user('publicador', ['soles_pricing.group_publisher'])
    f.cost_editor = user('costos', ['soles_pricing.group_cost_editor'])
    f.segment = env['soles.pricing.segment'].create({'name': 'Gold QA ' + uuid.uuid4().hex[:6]})
    f.brand = env['soles.pricing.brand'].create({'name': 'Marca QA ' + uuid.uuid4().hex[:6]})
    f.family = env['soles.pricing.family'].create({'name': 'Módulos QA', 'min_margin': 0, 'exception_margin': 0})
    f.partner = env['res.partner'].create({'name': 'Cliente QA', 'soles_segment_id': f.segment.id})
    f.product_policy = env['soles.pricing.product.policy'].create({'name': 'Precio revisado QA', 'allow_sale': True, 'allow_b2b': True})
    f.product = env['product.product'].create({'name': 'Módulo QA', 'default_code': 'QA-SP', 'list_price': 1500,
        'standard_price': 900, 'soles_family_id': f.family.id, 'soles_brand_id': f.brand.id,
        'soles_product_policy_id': f.product_policy.id, 'taxes_id': [Command.clear()]})
    f.pricelist = env['product.pricelist'].create({'name': 'Lista QA', 'company_id': f.company.id, 'currency_id': f.company.currency_id.id})
    f.partner.property_product_pricelist = f.pricelist
    f.base_rule = publish(env['soles.pricing.rule'].create({'name': 'Gold módulos QA', 'scope': 'segment', 'segment_id': f.segment.id,
        'family_id': f.family.id, 'method': 'fixed', 'fixed_price': 1350, 'currency_id': f.company.currency_id.id}))
    f.benefit = publish(env['soles.pricing.rule'].create({'name': 'Beneficio cliente QA', 'stage': 'benefit', 'scope': 'partner',
        'partner_id': f.partner.id, 'discount_pct': 2}))
    f.cost = publish(env['soles.pricing.cost'].create({'name': 'Reposición QA', 'product_id': f.product.id, 'amount': 1150,
        'currency_id': f.company.currency_id.id, 'date_start': fields.Date.today() - timedelta(days=30), 'source': 'replacement', 'source_reference': 'DOC-QA-001'}))
    f.seller_auth = env['soles.pricing.authority'].create({'name': 'Vendedor QA', 'operation': 'discount',
        'group_id': env.ref('soles_pricing.group_seller').id, 'max_discount': 3})
    f.approver_auth = env['soles.pricing.authority'].create({'name': 'Aprobar QA', 'operation': 'approve',
        'user_id': f.approver.id, 'max_discount': 10, 'min_margin': 5, 'override_floor': True,
        'override_manufacturer': True, 'allow_manual_quote': True})
    f.route = env['soles.pricing.route'].create({'name': 'Gerencia QA', 'reviewer_ids': [Command.set(f.approver.ids)]})
    f.company.write({'soles_discount_mode': 'sequential', 'soles_allow_benefit': True, 'soles_fx_mode': 'commercial',
        'soles_min_margin': 0, 'soles_require_cost': True, 'soles_allow_self_approval': False,
        'soles_approval_hours': 24, 'soles_notify_reviewers': True, 'soles_revalidate_cost': True, 'soles_pricing_mode': 'enforce'})
    return f


def order(f, price=None, user=None, lines=1, **values):
    user = user or f.seller
    vals = {'partner_id': f.partner.id, 'pricelist_id': f.pricelist.id, 'company_id': f.company.id, 'user_id': user.id,
        'order_line': [Command.create(dict(product_id=f.product.id, product_uom_qty=1, product_uom=f.product.uom_id.id,
            tax_id=[Command.clear()], **({'price_unit': price} if price is not None else {}))) for _ in range(lines)]}
    vals.update(values)
    return f.env['sale.order'].with_user(user).create(vals)


def request(line):
    line.write({'soles_request_reason': 'Precio para proyecto excepcional QA'})
    action = line.action_soles_request()
    return line.env['soles.pricing.approval'].browse(action['res_id'])


def approve(f, line, user=None):
    rec = request(line)
    actor = rec.with_user(user or f.approver)
    actor.write({'decision_reason': 'Margen y condiciones revisados QA'})
    actor.action_approve()
    return rec
