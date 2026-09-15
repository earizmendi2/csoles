# -*- coding: utf-8 -*-
"""
Utilidades de migración: renombrado de modelos técnicos del módulo.
Usado por pre-migrate (antes de cargar Python) y post-migrate (limpieza).
"""

import logging

_logger = logging.getLogger(__name__)

MODEL_RENAMES = (
    ('cif.parser', 'cs.partner.tax.certificate.parser'),
    ('sat.service', 'cs.partner.tax.certificate.sat.service'),
    ('import.from.cif.wizard', 'cs.partner.tax.certificate.import.wizard'),
    ('update.from.sat.wizard', 'cs.partner.tax.certificate.update.wizard'),
)

TABLE_RENAMES = (
    ('import_from_cif_wizard', 'cs_partner_tax_certificate_import_wizard'),
    ('update_from_sat_wizard', 'cs_partner_tax_certificate_update_wizard'),
)

OLD_ACCESS_XMLIDS = (
    'access_import_from_cif_wizard_user',
    'access_cif_parser_user',
    'access_update_from_sat_wizard_user',
    'access_sat_service_user',
)


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = %s
        """,
        (table_name,),
    )
    return bool(cr.fetchone())


def _model_id(cr, model_name):
    cr.execute('SELECT id FROM ir_model WHERE model = %s', (model_name,))
    row = cr.fetchone()
    return row[0] if row else None


def _update_model_references(cr, old_model, new_model, model_id):
    cr.execute('UPDATE ir_model SET model = %s WHERE id = %s', (new_model, model_id))
    cr.execute(
        'UPDATE ir_model_fields SET model = %s WHERE model = %s',
        (new_model, old_model),
    )
    cr.execute(
        'UPDATE ir_model_fields SET relation = %s WHERE relation = %s',
        (new_model, old_model),
    )
    cr.execute(
        'UPDATE ir_model_data SET model = %s WHERE model = %s',
        (new_model, old_model),
    )
    cr.execute(
        'UPDATE ir_ui_view SET model = %s WHERE model = %s',
        (new_model, old_model),
    )
    cr.execute(
        'UPDATE ir_act_window SET res_model = %s WHERE res_model = %s',
        (new_model, old_model),
    )


def _remove_duplicate_new_model(cr, old_model, new_model):
    """Si Odoo ya creó el modelo nuevo, eliminar el duplicado y conservar el antiguo."""
    old_id = _model_id(cr, old_model)
    new_id = _model_id(cr, new_model)
    if not old_id or not new_id or old_id == new_id:
        return
    _logger.warning(
        'cs_partner_tax_certificate: duplicado %s (id=%s) y %s (id=%s); '
        'eliminando registro nuevo.',
        old_model,
        old_id,
        new_model,
        new_id,
    )
    cr.execute('DELETE FROM ir_model_fields WHERE model_id = %s', (new_id,))
    cr.execute('DELETE FROM ir_model WHERE id = %s', (new_id,))


def rename_models(cr):
    for old_model, new_model in MODEL_RENAMES:
        _remove_duplicate_new_model(cr, old_model, new_model)
        old_id = _model_id(cr, old_model)
        if not old_id:
            continue
        _logger.info(
            'cs_partner_tax_certificate: modelo %s → %s (id=%s)',
            old_model,
            new_model,
            old_id,
        )
        _update_model_references(cr, old_model, new_model, old_id)


def rename_wizard_tables(cr):
    for old_table, new_table in TABLE_RENAMES:
        if _table_exists(cr, old_table) and not _table_exists(cr, new_table):
            _logger.info(
                'cs_partner_tax_certificate: tabla %s → %s',
                old_table,
                new_table,
            )
            cr.execute(
                'ALTER TABLE "%s" RENAME TO "%s"' % (old_table, new_table)
            )


def cleanup_old_access_rules(cr):
    cr.execute(
        """
        DELETE FROM ir_model_access
        WHERE id IN (
            SELECT d.res_id
            FROM ir_model_data d
            WHERE d.module = 'cs_partner_tax_certificate'
              AND d.model = 'ir.model.access'
              AND d.name = ANY(%s)
        )
        """,
        (list(OLD_ACCESS_XMLIDS),),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'cs_partner_tax_certificate'
          AND model = 'ir.model.access'
          AND name = ANY(%s)
        """,
        (list(OLD_ACCESS_XMLIDS),),
    )


def run_pre(cr):
    rename_models(cr)
    rename_wizard_tables(cr)


def run_post(cr):
    _remove_duplicate_new_models_all(cr)
    rename_models(cr)
    rename_wizard_tables(cr)
    cleanup_old_access_rules(cr)


def _remove_duplicate_new_models_all(cr):
    for old_model, new_model in MODEL_RENAMES:
        _remove_duplicate_new_model(cr, old_model, new_model)
