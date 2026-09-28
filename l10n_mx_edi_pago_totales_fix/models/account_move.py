# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import float_round


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        """Corrige los Totales del complemento de pago (CRP20204/CRP20205).

        CAUSA RAÍZ (confirmada con evidencia real, no supuesta - ver
        conversación de soporte del 2026-09-28): en la versión actual de
        l10n_mx_edi, BaseP/ImporteP (lo que se imprime en cada TrasladoP/
        RetencionP) y los Totales se calculan por dos caminos INDEPENDIENTES
        a partir de las líneas de impuestos de cada factura, cada uno con su
        propio redondeo a 6 decimales en distinto orden de operaciones. El
        SAT exige Totales = round(BaseP_impreso x TipoCambioP), pero el
        camino de Totales del core nunca pasa por el BaseP que realmente se
        imprime, así que pueden divergir por centavos.

        Aquí, después de que el core hace todo su trabajo normal, se
        recalculan los 10 campos de Totales directamente desde BaseP/
        ImporteP ya calculados, a la MISMA precisión con que realmente se
        imprimen en el XML:
          - BaseP se imprime a la precisión de la moneda (currency_precision,
            normalmente 2).
          - ImporteP se imprime a 6 decimales (parche histórico de Odoo para
            CRP20274 - ver el "dirty fix" en l10n_mx_edi_document.py).
        Así los Totales quedan garantizados por construcción, sin importar
        qué haga el camino paralelo del core.
        """
        res = super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        if cfdi_values.get('errors'):
            return res

        company_curr = cfdi_values['company'].currency_id
        pay_rate = cfdi_values.get('tipo_cambio') or 1.0
        base_dp = cfdi_values.get('currency_precision')
        if base_dp is None:
            base_dp = company_curr.decimal_places
        importe_dp = 6  # precisión con que se imprime ImporteP (parche CRP20274)

        total_keys = (
            'total_traslados_base_iva0', 'total_traslados_impuesto_iva0',
            'total_traslados_base_iva_exento',
            'total_traslados_base_iva8', 'total_traslados_impuesto_iva8',
            'total_traslados_base_iva16', 'total_traslados_impuesto_iva16',
            'total_retenciones_isr', 'total_retenciones_iva', 'total_retenciones_ieps',
        )
        for key in total_keys:
            cfdi_values[key] = None

        def add_total(key, amount):
            if amount is None:
                return
            cfdi_values[key] = (cfdi_values[key] or 0.0) + amount

        def is_transferred(tax, tag, factor, rate):
            return (
                tax.get('impuesto') == tag
                and tax.get('tipo_factor') == factor
                and company_curr.compare_amounts(tax.get('tasa_o_cuota') or 0.0, rate) == 0
            )

        for list_key in ('traslados_list', 'local_traslados_list'):
            for tax in cfdi_values.get(list_key) or []:
                base_printed = None
                if tax.get('base') is not None:
                    base_printed = float_round(tax['base'], precision_digits=base_dp)
                importe_printed = None
                if tax.get('importe') is not None:
                    importe_printed = float_round(tax['importe'], precision_digits=importe_dp)

                base_mxn = base_printed * pay_rate if base_printed is not None else None
                importe_mxn = importe_printed * pay_rate if importe_printed is not None else None

                if is_transferred(tax, '002', 'Tasa', 0.0):
                    add_total('total_traslados_base_iva0', base_mxn)
                    add_total('total_traslados_impuesto_iva0', importe_mxn)
                elif is_transferred(tax, '002', 'Exento', 0.0):
                    add_total('total_traslados_base_iva_exento', base_mxn)
                elif is_transferred(tax, '002', 'Tasa', 0.08):
                    add_total('total_traslados_base_iva8', base_mxn)
                    add_total('total_traslados_impuesto_iva8', importe_mxn)
                elif is_transferred(tax, '002', 'Tasa', 0.16):
                    add_total('total_traslados_base_iva16', base_mxn)
                    add_total('total_traslados_impuesto_iva16', importe_mxn)

        for list_key in ('retenciones_list', 'local_retenciones_list'):
            for tax in cfdi_values.get(list_key) or []:
                if tax.get('importe') is None:
                    continue
                importe_printed = float_round(tax['importe'], precision_digits=importe_dp)
                importe_mxn = importe_printed * pay_rate

                if tax.get('impuesto') == '001':
                    add_total('total_retenciones_isr', importe_mxn)
                elif tax.get('impuesto') == '002':
                    add_total('total_retenciones_iva', importe_mxn)
                elif tax.get('impuesto') == '003':
                    add_total('total_retenciones_ieps', importe_mxn)

        for key in total_keys:
            if cfdi_values[key] is not None:
                cfdi_values[key] = company_curr.round(cfdi_values[key])

        return res
