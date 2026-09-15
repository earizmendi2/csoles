# -*- coding: utf-8 -*-
"""En cada subida de versión del módulo: columna sat_url si falta (idempotente)."""


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
    cr.execute('ALTER TABLE res_partner ADD COLUMN sat_url varchar NULL')
