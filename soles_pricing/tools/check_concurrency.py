"""Run ONLY in a disposable installed database via `odoo-bin shell < this_file`.
Creates a complete example fixture; commits it, races two independent connections,
and asserts one consumption. Never run against a production database.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from odoo import api
from odoo.addons.soles_pricing.tests.common import build_fixture, order, approve


def run(env):
    if not env.cr.dbname.startswith('soles_pricing_'):
        raise RuntimeError('Use una base desechable soles_pricing_*; este control crea datos de prueba.')
    env = api.Environment(env.cr, 1, dict(env.context, mail_notify_force_send=False, tracking_disable=True), su=True)
    f = build_fixture(env)
    quote = order(f, 1250)
    authorization = approve(f, quote.order_line)
    quote.sudo().message_subscribe(partner_ids=quote.partner_id.ids)
    quote_id, auth_id, user_id = quote.id, authorization.id, f.seller.id
    registry = env.registry
    env.cr.commit()
    barrier = threading.Barrier(2)

    def confirm(label):
        with registry.cursor() as cr:
            current = api.Environment(cr, user_id, {'allowed_company_ids': f.company.ids, 'mail_notify_force_send': False})
            target = current['sale.order'].browse(quote_id)
            assert target.state == 'draft'
            barrier.wait(timeout=20)
            try:
                target.action_confirm()
                cr.commit()
                return {'worker': label, 'result': 'confirmed'}
            except Exception as exc:
                cr.rollback()
                return {'worker': label, 'result': 'rejected', 'exception': type(exc).__name__, 'message': str(exc).splitlines()[0]}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, ('A', 'B')))
    env.cr.rollback()
    env.invalidate_all()
    authorization = env['soles.pricing.approval'].browse(auth_id)
    quote = env['sale.order'].browse(quote_id)
    assert sum(r['result'] == 'confirmed' for r in results) == 1, results
    loser = next(r for r in results if r['result'] == 'rejected')
    assert loser['exception'] in ('SerializationFailure', 'UserError'), results
    assert quote.state == 'sale', quote.state
    assert authorization.state == 'consumed', authorization.state
    assert authorization.consumption_count == 1, authorization.consumption_count
    assert len(quote.picking_ids) == 1, 'No debe duplicar entregas'
    print('SOLES_CONCURRENCY_RESULT=' + json.dumps({'database': env.cr.dbname, 'workers': results,
        'order_state': quote.state, 'approval_state': authorization.state, 'consumption_count': authorization.consumption_count,
        'pickings': len(quote.picking_ids)}, ensure_ascii=False))


if 'env' in globals():
    run(env)
