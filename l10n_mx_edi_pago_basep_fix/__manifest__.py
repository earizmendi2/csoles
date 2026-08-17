{
    'name': 'CFDI Pagos 2.0 - Corrección BaseP/ImporteP (CRP20268)',
    'version': '18.0.1.0.0',
    'summary': (
        'Recalcula BaseP/ImporteP e ImpuestosP del complemento de pago a partir '
        'de los BaseDR/ImporteDR redondeados que realmente se imprimen, evitando '
        'el error CRP20268 en pagos de facturas en moneda extranjera.'
    ),
    'description': """
Corrección del complemento de pago (Pagos 2.0) para CRP20268
============================================================

En pagos de facturas en moneda extranjera (p. ej. factura en USD pagada en MXN),
Odoo calcula BaseP/ImporteP del nodo ImpuestosP a partir de los importes internos
sin redondear, mientras que los nodos DoctoRelacionado (BaseDR/ImporteDR) se
imprimen a 2 decimales. El SAT revalida BaseP = BaseDR ÷ EquivalenciaDR usando el
valor impreso, por lo que ambos no coinciden y rechaza el CFDI con CRP20268.

Este módulo, después de ejecutar la lógica estándar, recalcula:

* BaseP / ImporteP de cada TrasladoP / RetencionP como la suma de los
  BaseDR / ImporteDR (ya redondeados a los decimales con que se imprimen)
  divididos entre la EquivalenciaDR de cada documento, con 6 decimales.
* Los Totales (en MXN) de forma consistente con los nuevos ImpuestosP.

No modifica facturas, pagos ni asientos contables: solo la forma de expresar los
importes en el XML del complemento de pago.
""",
    'category': 'Accounting/Localizations/EDI',
    'author': 'AsesoraIT',
    'license': 'LGPL-3',
    'depends': ['l10n_mx_edi'],
    'installable': True,
    'auto_install': False,
}
