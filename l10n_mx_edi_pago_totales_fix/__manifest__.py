# -*- coding: utf-8 -*-
{
    'name': 'CFDI Pagos 2.0 - Corrección de Totales (CRP20204/CRP20205)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': (
        'Recalcula los Totales del complemento de pago directamente desde '
        'BaseP/ImporteP (lo que realmente se imprime), evitando CRP20204 y '
        'CRP20205 causados por un cálculo paralelo divergente en el core.'
    ),
    'description': """
Corrección de Totales del complemento de pago (CRP20204 / CRP20205)
=======================================================================

CAUSA RAÍZ CONFIRMADA (con evidencia real, no supuesta): en la versión de
l10n_mx_edi actualmente en ejecución, BaseP/ImporteP (lo que se imprime en
cada TrasladoP/RetencionP) y los Totales del complemento (TotalTraslados...)
se calculan por DOS CAMINOS INDEPENDIENTES a partir de las líneas de
impuestos de cada factura:

* BaseP/ImporteP: se agrupan dividiendo cada línea entre 'equivalencia'
  (tasa de la factura respecto al pago).
* Totales: se agrupan por separado, multiplicando cada línea cruda por
  (TipoCambioP / equivalencia) directamente — SIN pasar por el valor de
  BaseP/ImporteP ya calculado.

Cada camino redondea de forma independiente (a 6 decimales, en distinto
orden de operaciones), así que pueden divergir por centavos. El SAT exige
literalmente que Totales = round(BaseP_impreso x TipoCambioP), pero el
camino de Totales nunca pasa por el BaseP que realmente se imprime — de
ahí los rechazos CRP20204 (Base) y CRP20205 (Importe).

Este módulo corre después de la lógica estándar (no la reemplaza) y
recalcula los 10 campos de Totales directamente desde BaseP/ImporteP ya
calculados (redondeados a la precisión con que se imprimen), multiplicados
por TipoCambioP, garantizando por construcción que coincidan con lo que el
SAT revalida desde el XML.

No modifica BaseP, ImporteP, ni ningún otro dato de facturas/pagos: solo
los 10 campos de Totales del complemento de pago.
""",
    'author': 'Rubén Castillo',
    'license': 'LGPL-3',
    'depends': ['l10n_mx_edi'],
    'installable': True,
    'auto_install': False,
}
