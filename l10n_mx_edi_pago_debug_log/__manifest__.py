# -*- coding: utf-8 -*-
{
    'name': 'CFDI Pagos - Diagnóstico (solo logging, no corrige nada)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': (
        'Registra en el log del servidor los valores reales que calcula '
        '_l10n_mx_edi_add_payment_cfdi_values, para diagnosticar errores de '
        'redondeo tipo CRP20204/CRP20205 la próxima vez que ocurran.'
    ),
    'description': """
Diagnóstico de errores de redondeo en Pagos 2.0 (CRP20204 / CRP20205)
=======================================================================

Este módulo NO modifica ningún cálculo del core ni cambia ningún número en
el CFDI. Únicamente hereda _l10n_mx_edi_add_payment_cfdi_values, deja que el
core haga todo su trabajo normal, y al final escribe en el log del servidor
(nivel WARNING para que sea fácil de filtrar) los valores clave que se
usaron: TipoCambioP, precisión de moneda, y el detalle de BaseP/ImporteP
por cada TrasladoP/RetencionP antes y después de aplicar el tipo de cambio.

Objetivo: la próxima vez que aparezca un CRP20204 o CRP20205, tener los
valores reales capturados en el momento exacto del cálculo, en vez de tener
que reconstruirlos después con el shell (cuando la conciliación ya pudo
haber cambiado y el caso deja de ser reproducible).

Se puede desactivar sin desinstalar el módulo, mediante el parámetro de
sistema 'l10n_mx_edi_pago_debug_log.enabled' (poner en 'False' para
silenciarlo). Por defecto está activo.

Una vez que se capture un caso real con el bug y se entienda la causa raíz,
este módulo debe reemplazarse por el módulo de corrección definitivo (y
podrá desinstalarse).
""",
    'author': 'Rubén Castillo',
    'license': 'LGPL-3',
    'depends': ['l10n_mx_edi'],
    'installable': True,
    'auto_install': False,
}
