# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger('l10n_mx_edi_pago_debug_log')

# Impuestos trasladados que el SAT valida en el nodo Totales, con su tag
# (impuesto, tipo_factor, tasa) -> nombre del campo total en cfdi_values.
_TRASLADO_TOTAL_MAP = {
    ('002', 'Tasa', 0.0): ('total_traslados_base_iva0', 'total_traslados_impuesto_iva0'),
    ('002', 'Tasa', 0.08): ('total_traslados_base_iva8', 'total_traslados_impuesto_iva8'),
    ('002', 'Tasa', 0.16): ('total_traslados_base_iva16', 'total_traslados_impuesto_iva16'),
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        # Deja que el core haga TODO el trabajo normal, sin tocar nada.
        res = super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        if not self._l10n_mx_edi_pago_debug_log_enabled():
            return res

        if cfdi_values.get('errors'):
            _logger.warning(
                'CFDI Pagos DEBUG [%s]: el core reportó errores, no se '
                'genera el diagnóstico: %s',
                self.name, cfdi_values['errors'],
            )
            return res

        try:
            self._l10n_mx_edi_pago_debug_log(cfdi_values)
        except Exception:  # noqa: BLE001 - el logging nunca debe romper el timbrado
            _logger.exception(
                'CFDI Pagos DEBUG [%s]: error generando el diagnóstico '
                '(no afecta el timbrado, es solo logging).', self.name,
            )

        return res

    def _l10n_mx_edi_pago_debug_log_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'l10n_mx_edi_pago_debug_log.enabled', 'True'
        ) not in ('False', 'false', '0')

    def _l10n_mx_edi_pago_debug_log(self, cfdi_values):
        self.ensure_one()
        pay_rate = cfdi_values.get('tipo_cambio') or 1.0
        company_curr = cfdi_values['company'].currency_id
        pay_curr_dp = cfdi_values.get('currency_precision')

        lines = []
        lines.append('=== CFDI Pagos DEBUG [%s] ===' % self.name)
        lines.append('  tipo_cambio (TipoCambioP): %r' % pay_rate)
        lines.append('  currency_precision: %r' % pay_curr_dp)
        lines.append('  monto_total_pagos: %r' % cfdi_values.get('monto_total_pagos'))

        # -- Documentos relacionados (DoctoRelacionado): base cruda por factura --
        for doc in cfdi_values.get('docto_relationado_list') or []:
            lines.append(
                '  DoctoRelacionado id_documento=%s equivalencia=%r' % (
                    doc.get('id_documento'), doc.get('equivalencia'),
                )
            )
            for dr_key in ('traslados_list', 'retenciones_list',
                           'local_traslados_list', 'local_retenciones_list'):
                for t in doc.get(dr_key) or []:
                    if t.get('base') is None and t.get('importe') is None:
                        continue
                    lines.append(
                        '      %s: impuesto=%s tipo_factor=%s tasa=%r base=%r importe=%r' % (
                            dr_key, t.get('impuesto'), t.get('tipo_factor'),
                            t.get('tasa_o_cuota'), t.get('base'), t.get('importe'),
                        )
                    )

        # -- ImpuestosP (lo que realmente se imprime como BaseP/ImporteP) --
        for p_key in ('traslados_list', 'retenciones_list',
                      'local_traslados_list', 'local_retenciones_list'):
            for t in cfdi_values.get(p_key) or []:
                lines.append(
                    '  %s (ImpuestosP): impuesto=%s tipo_factor=%s tasa=%r '
                    'base=%r importe=%r' % (
                        p_key, t.get('impuesto'), t.get('tipo_factor'),
                        t.get('tasa_o_cuota'), t.get('base'), t.get('importe'),
                    )
                )

        # -- Totales reportados vs. los que recalculamos aquí a partir de --
        # -- BaseP/ImporteP (lo impreso) x TipoCambioP, para detectar --
        # -- cualquier discrepancia con lo que exige el SAT. --
        for (impuesto, tipo_factor, tasa), (base_key, importe_key) in _TRASLADO_TOTAL_MAP.items():
            base_sum = 0.0
            importe_sum = 0.0
            for p_key in ('traslados_list', 'local_traslados_list'):
                for t in cfdi_values.get(p_key) or []:
                    if (
                        t.get('impuesto') == impuesto
                        and t.get('tipo_factor') == tipo_factor
                        and company_curr.compare_amounts(t.get('tasa_o_cuota') or 0.0, tasa) == 0
                    ):
                        if t.get('base') is not None:
                            base_sum += t['base'] * pay_rate
                        if t.get('importe') is not None:
                            importe_sum += t['importe'] * pay_rate

            if base_sum or importe_sum or cfdi_values.get(base_key) is not None:
                esperado_base = company_curr.round(base_sum) if base_sum else None
                esperado_importe = company_curr.round(importe_sum) if importe_sum else None
                reportado_base = cfdi_values.get(base_key)
                reportado_importe = cfdi_values.get(importe_key)

                lines.append(
                    '  %s: reportado=%r  recalculado_desde_BaseP_impreso=%r  '
                    '%s' % (
                        base_key, reportado_base, esperado_base,
                        '<<< DISCREPANCIA >>>'
                        if reportado_base is not None and esperado_base is not None
                        and company_curr.compare_amounts(reportado_base, esperado_base) != 0
                        else 'OK',
                    )
                )
                lines.append(
                    '  %s: reportado=%r  recalculado_desde_ImporteP_impreso=%r  '
                    '%s' % (
                        importe_key, reportado_importe, esperado_importe,
                        '<<< DISCREPANCIA >>>'
                        if reportado_importe is not None and esperado_importe is not None
                        and company_curr.compare_amounts(reportado_importe, esperado_importe) != 0
                        else 'OK',
                    )
                )

        lines.append('=== FIN CFDI Pagos DEBUG [%s] ===' % self.name)
        _logger.warning('\n'.join(lines))
