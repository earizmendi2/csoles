"""Upgrade preliminary releases without silently activating the new policy."""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("UPDATE res_company SET soles_pricing_mode='off', soles_discount_mode='sequential'")
    _logger.info('SOLES MIGRATION: previous companies moved to Nativo for commercial review; native sales prices retained.')
