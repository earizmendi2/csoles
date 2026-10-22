import logging
import uuid
from odoo import api, SUPERUSER_ID
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model in ('soles.pricing.rule', 'soles.pricing.cost', 'soles.pricing.fx', 'soles.pricing.limit'):
        records = env[model].with_context(active_test=False).search([('version_id', '=', False)])
        for record in records:
            # Give each preliminary document an independent series. Do not invent
            # a publisher, approval or commercial source for legacy values.
            cr.execute('UPDATE ' + record._table + " SET state='draft', series_key=%s WHERE id=%s", [str(uuid.uuid4()), record.id])
        _logger.info('SOLES MIGRATION: %s documents awaiting review in %s', len(records), model)
    requests = env['soles.pricing.approval'].search([('state', 'in', ['pending', 'approved'])])
    requests.write({'state': 'invalid'})
    # Immutable historic company/currency, including cancelled/consumed history.
    cr.execute('''UPDATE soles_pricing_approval a SET company_id=o.company_id,
                  currency_id=o.currency_id, company_currency_id=c.currency_id
                  FROM sale_order o JOIN res_company c ON c.id=o.company_id WHERE a.order_id=o.id''')
    cr.execute("UPDATE soles_pricing_approval SET consumption_count=1 WHERE state='consumed' AND consumption_count=0")
    env.invalidate_all()
    _logger.info('SOLES MIGRATION: %s pending/approved preliminary authorizations invalidated. A/B/C/D not mapped automatically.', len(requests))
