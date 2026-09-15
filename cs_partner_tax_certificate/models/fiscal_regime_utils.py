# -*- coding: utf-8 -*-
"""Selección de régimen fiscal alineada con Odoo Enterprise (l10n_mx_edi) cuando exista."""

# Catálogo SAT (México). Se usa en ``res.partner.fiscal_regime`` para Community
# y como respaldo cuando no hay otro campo Selection de régimen en el modelo.
FISCAL_REGIME_SAT_SELECTION = [
    ('601', 'General de Ley Personas Morales'),
    ('603', 'Personas Morales con Fines no Lucrativos'),
    ('605', 'Sueldos y Salarios e Ingresos Asimilados a Salarios'),
    ('606', 'Arrendamiento'),
    ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
    ('608', 'Demás ingresos'),
    ('609', 'Consolidación'),
    ('610', 'Residentes en el Extranjero sin Establecimiento Permanente en México'),
    ('611', 'Ingresos por Dividendos (socios y accionistas)'),
    ('612', 'Personas Físicas con Actividades Empresariales y Profesionales'),
    ('614', 'Ingresos por intereses'),
    ('615', 'Régimen de los ingresos por obtención de premios'),
    ('616', 'Sin obligaciones fiscales'),
    ('620', 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos'),
    ('621', 'Incorporación Fiscal'),
    ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
    ('623', 'Opcional para Grupos de Sociedades'),
    ('624', 'Coordinados'),
    ('625', 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas'),
    ('626', 'Régimen Simplificado de Confianza - RESICO'),
    ('628', 'Hidrocarburos'),
    ('629', 'De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales'),
    ('630', 'Enajenación de acciones en bolsa de valores'),
]


def partner_has_fiscal_regime_selection_field(env):
    """True si hay campo Selection de régimen (EE, addon MX o el de este módulo)."""
    for fname in ('l10n_mx_edi_fiscal_regime', 'fiscal_regime'):
        f = env['res.partner']._fields.get(fname)
        if f and f.type == 'selection':
            return True
    return False


def get_mx_fiscal_regime_selection(env):
    """
    Devuelve la misma lista (código, etiqueta) que el campo estándar
    ``l10n_mx_edi_fiscal_regime`` en ``res.partner`` cuando el módulo
    ``l10n_mx_edi`` está instalado; si no, intenta importar la constante
    del código fuente; en último caso usa un catálogo equivalente al SAT.
    """
    partner_model = env['res.partner']
    for fname in ('l10n_mx_edi_fiscal_regime', 'fiscal_regime'):
        field = partner_model._fields.get(fname)
        if not field or field.type != 'selection':
            continue
        sel = field.selection
        pairs = sel(partner_model) if callable(sel) else sel
        if pairs:
            return list(pairs)
    try:
        from odoo.addons.l10n_mx_edi.models.res_company import (
            FISCAL_REGIMES_SELECTION,
        )

        return list(FISCAL_REGIMES_SELECTION)
    except ImportError:
        return list(FISCAL_REGIME_SAT_SELECTION)
