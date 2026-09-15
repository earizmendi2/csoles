# -*- coding: utf-8 -*-
"""Mensajes amigables para dependencias externas y errores frecuentes."""

from odoo import _


def msg_missing_pypdf2():
    return _(
        'No se pudo leer el PDF porque falta la librería PyPDF2.\n\n'
        'Instálela en el entorno Python de Odoo con:\n'
        'pip install PyPDF2'
    )


def msg_missing_fitz():
    return _(
        'No se pudo procesar el PDF para leer el código QR porque falta PyMuPDF (fitz).\n\n'
        'Instálela con:\n'
        'pip install pymupdf'
    )


def msg_missing_pyzbar():
    return _(
        'No fue posible leer el código QR de la constancia porque falta la librería pyzbar.\n\n'
        'Instálela con:\n'
        'pip install pyzbar Pillow'
    )


def msg_missing_libzbar():
    return _(
        'No fue posible leer el código QR de la constancia.\n\n'
        'Verifique que la librería del sistema libzbar0 esté instalada en el servidor.\n'
        'En Ubuntu/Debian puede instalarse con:\n\n'
        'sudo apt install libzbar0\n\n'
        'Después reinicie el servicio de Odoo.'
    )


def msg_pdf_invalid(detail=''):
    base = _('El archivo no es un PDF válido o está dañado.')
    return '%s\n%s' % (base, detail) if detail else base


def msg_pdf_no_qr():
    return _(
        'No se encontró un código QR con URL de verificación en el PDF.\n\n'
        'Verifique que sea una Constancia de Situación Fiscal emitida por el SAT '
        'y que el documento no esté escaneado con baja calidad.'
    )


def msg_sat_url_not_found():
    return _(
        'No hay URL de verificación del SAT en el contacto.\n\n'
        'Importe primero la constancia en PDF para extraer la URL del código QR, '
        'o registre manualmente la URL oficial de siat.sat.gob.mx.'
    )


def msg_sat_unavailable():
    return _(
        'El portal del SAT no está disponible en este momento.\n\n'
        'Intente nuevamente más tarde. La consulta se realiza únicamente hacia '
        'siat.sat.gob.mx desde su servidor de Odoo.'
    )


def msg_sat_format_changed():
    return _(
        'El SAT respondió, pero no fue posible interpretar los datos fiscales.\n\n'
        'Es posible que el portal haya cambiado su formato o que la constancia '
        'haya expirado. Verifique la URL manualmente en el navegador.'
    )


def msg_missing_bs4():
    return _(
        'No se pudo analizar la respuesta del SAT porque falta beautifulsoup4.\n\n'
        'Instálela con:\n'
        'pip install beautifulsoup4'
    )


def msg_missing_requests():
    return _(
        'No se pudo consultar el SAT porque falta la librería requests.\n\n'
        'Instálela con:\n'
        'pip install requests certifi truststore'
    )


def is_libzbar_missing_error(exc):
    """Detecta errores típicos cuando libzbar0 no está instalado."""
    if exc is None:
        return False
    text = str(exc).lower()
    markers = (
        'libzbar',
        'zbar',
        'cannot find',
        'failed to load',
        'shared object',
        'dll load',
        'no such file',
    )
    return any(m in text for m in markers)


def qr_dependency_warning(import_ok):
    """
    Devuelve aviso para el usuario según qué dependencias de QR faltan.

    :param import_ok: dict con claves pymupdf, pyzbar, libzbar (bool).
    """
    if not import_ok.get('pymupdf'):
        return msg_missing_fitz()
    if not import_ok.get('pyzbar'):
        return msg_missing_pyzbar()
    if not import_ok.get('libzbar'):
        return msg_missing_libzbar()
    return msg_pdf_no_qr()
