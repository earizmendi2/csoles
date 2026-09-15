# -*- coding: utf-8 -*-
"""Garantiza columnas del módulo en res_partner (evita UndefinedColumn tras upgrades parciales)."""


def migrate(cr, version):
    for colname in ('fiscal_regime', 'sat_url'):
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'res_partner'
              AND column_name = %s
            """,
            (colname,),
        )
        if cr.fetchone():
            continue
        cr.execute(
            'ALTER TABLE res_partner ADD COLUMN "%s" varchar NULL' % colname
        )
