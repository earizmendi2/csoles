from odoo import models
from odoo.tools import float_round


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        """Corrige BaseP/ImporteP (y los Totales) del complemento de pago.

        El estándar calcula el nodo ImpuestosP (BaseP/ImporteP) a partir de los
        importes internos SIN redondear, mientras que los nodos DoctoRelacionado
        (BaseDR/ImporteDR) se imprimen a los decimales de la moneda (2 en MX).
        El SAT revalida BaseP = BaseDR ÷ EquivalenciaDR usando el valor IMPRESO,
        de modo que ambos no coinciden en pagos multimoneda -> CRP20268.

        Aquí, tras ejecutar la lógica estándar, recalculamos ImpuestosP y los
        Totales desde los BaseDR/ImporteDR ya redondeados.
        """
        # 1) Ejecuta la lógica estándar de Odoo.
        res = super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        # Si el estándar detectó errores, no tocamos nada.
        if cfdi_values.get('errors'):
            return res

        company_curr = cfdi_values['company'].currency_id
        pay_rate = cfdi_values.get('tipo_cambio') or 1.0
        docs = cfdi_values.get('docto_relationado_list') or []

        # Decimales con que se IMPRIMEN los nodos DoctoRelacionado (BaseDR/ImporteDR).
        # Debe coincidir con la precisión del format_float de la plantilla.
        # La plantilla estándar de Odoo 18 imprime BaseDR/ImporteDR con precision=6,
        # así que aquí también usamos 6 para replicar el cálculo del SAT
        # (BaseP = suma de los BaseDR de 6 decimales ÷ EquivalenciaDR).
        dr_dp = 6

        dr_lists = (
            'retenciones_list', 'traslados_list',
            'local_retenciones_list', 'local_traslados_list',
        )

        # 1) Redondea los importes de cada DoctoRelacionado a la precisión impresa,
        #    de forma que el valor almacenado sea idéntico al que ve el SAT.
        for doc in docs:
            for dr_key in dr_lists:
                for d_tax in doc.get(dr_key) or []:
                    if d_tax.get('base') is not None:
                        d_tax['base'] = float_round(d_tax['base'], precision_digits=dr_dp)
                    if d_tax.get('importe') is not None:
                        d_tax['importe'] = float_round(d_tax['importe'], precision_digits=dr_dp)

        # 2) Recalcula BaseP/ImporteP de cada línea de ImpuestosP como la suma de
        #    los BaseDR/ImporteDR (ya redondeados) ÷ EquivalenciaDR, con 6 decimales.
        #    - Traslados: se agrupan por impuesto + tipo de factor + tasa/cuota.
        #    - Retenciones: se agrupan por impuesto (el nodo RetencionP no lleva tasa).
        specs = (
            ('traslados_list', 'traslados_list', True),
            ('retenciones_list', 'retenciones_list', False),
            ('local_traslados_list', 'local_traslados_list', True),
            ('local_retenciones_list', 'local_retenciones_list', False),
        )
        for p_key, dr_key, has_base in specs:
            for p_tax in cfdi_values.get(p_key) or []:
                base_sum = 0.0
                importe_sum = 0.0
                for doc in docs:
                    inv_rate = doc.get('equivalencia') or 1.0
                    for d_tax in doc.get(dr_key) or []:
                        if d_tax.get('impuesto') != p_tax.get('impuesto'):
                            continue
                        if has_base and (
                            d_tax.get('tipo_factor') != p_tax.get('tipo_factor')
                            or company_curr.compare_amounts(
                                d_tax.get('tasa_o_cuota') or 0.0,
                                p_tax.get('tasa_o_cuota') or 0.0,
                            ) != 0
                        ):
                            continue
                        if has_base and d_tax.get('base') is not None:
                            base_sum += (d_tax['base'] / inv_rate) if inv_rate else 0.0
                        if d_tax.get('importe') is not None:
                            importe_sum += (d_tax['importe'] / inv_rate) if inv_rate else 0.0
                if has_base:
                    p_tax['base'] = float_round(base_sum, precision_digits=6) or 0.000001
                # 'importe' es None para Exento; en ese caso no se toca.
                if p_tax.get('importe') is not None:
                    p_tax['importe'] = float_round(importe_sum, precision_digits=6)

        # 3) Recalcula los Totales (en MXN) de forma consistente con ImpuestosP.
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
            cfdi_values[key] = (cfdi_values[key] or 0.0) + amount * pay_rate

        def is_transferred(tax, tag, factor, rate):
            return (
                tax.get('impuesto') == tag
                and tax.get('tipo_factor') == factor
                and company_curr.compare_amounts(tax.get('tasa_o_cuota') or 0.0, rate) == 0
            )

        for key in ('traslados_list', 'local_traslados_list'):
            for tax in cfdi_values.get(key) or []:
                if is_transferred(tax, '002', 'Tasa', 0.0):
                    add_total('total_traslados_base_iva0', tax.get('base'))
                    add_total('total_traslados_impuesto_iva0', tax.get('importe'))
                elif is_transferred(tax, '002', 'Exento', 0.0):
                    add_total('total_traslados_base_iva_exento', tax.get('base'))
                elif is_transferred(tax, '002', 'Tasa', 0.08):
                    add_total('total_traslados_base_iva8', tax.get('base'))
                    add_total('total_traslados_impuesto_iva8', tax.get('importe'))
                elif is_transferred(tax, '002', 'Tasa', 0.16):
                    add_total('total_traslados_base_iva16', tax.get('base'))
                    add_total('total_traslados_impuesto_iva16', tax.get('importe'))

        for key in ('retenciones_list', 'local_retenciones_list'):
            for tax in cfdi_values.get(key) or []:
                if tax.get('impuesto') == '001':
                    add_total('total_retenciones_isr', tax.get('importe'))
                elif tax.get('impuesto') == '002':
                    add_total('total_retenciones_iva', tax.get('importe'))
                elif tax.get('impuesto') == '003':
                    add_total('total_retenciones_ieps', tax.get('importe'))

        for key in total_keys:
            if cfdi_values[key] is not None:
                cfdi_values[key] = company_curr.round(cfdi_values[key])

        return res
