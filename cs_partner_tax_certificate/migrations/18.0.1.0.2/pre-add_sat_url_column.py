# -*- coding: utf-8 -*-
"""Garantiza la columna sat_url en res_partner antes del init_models del upgrade."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'res_partner'
          AND column_name = 'sat_url'
        """
    )
    if cr.fetchone():
        return
    _logger.info(
        'cs_partner_tax_certificate: creando columna faltante res_partner.sat_url'
    )
    cr.execute('ALTER TABLE res_partner ADD COLUMN sat_url varchar NULL')
