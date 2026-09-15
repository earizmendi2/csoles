# -*- coding: utf-8 -*-
"""Extracción de domicilio fiscal desde texto de PDF (constancia CIF). Solo PDF."""

import re

from .partner_address_utils import (
    format_geo_title,
    normalize_exterior_number,
    normalize_interior_number,
    sanitize_nombre_vialidad,
)

_FLAGS = re.IGNORECASE | re.UNICODE

# Etiquetas partidas en varias líneas (PyPDF2 suele cortar el texto así)
_LABEL_JOIN_PATTERNS = (
    (r'Nombre\s+de\s+la\s*\n\s*Localidad\s*:', 'Nombre de la Localidad:'),
    (
        r'Nombre\s+del\s+Municipio\s+o\s*\n\s*Demarcaci[oó]n\s+Territorial\s*:',
        'Nombre del Municipio o Demarcación Territorial:',
    ),
    (
        r'Nombre\s+del\s+Municipio\s+o\s*Demarcaci[oó]n\s*\n\s*Territorial\s*:',
        'Nombre del Municipio o Demarcación Territorial:',
    ),
    (
        r'Nombre\s+de\s+la\s*\n\s*Entidad\s+Federativa\s*:',
        'Nombre de la Entidad Federativa:',
    ),
    (r'Nombre\s+de\s+la\s*\n\s*Colonia\s*:', 'Nombre de la Colonia:'),
    (r'N[uú]mero\s*\n\s*Interior\s*:', 'Número Interior:'),
    (r'C[oó]digo\s*\n\s*Postal\s*:', 'Código Postal:'),
)

_RE_TIPO_VIALIDAD = re.compile(
    r'Tipo\s*de\s*Vialidad\s*:\s*([^\n\t]+?)(?=\s*Nombre\s*de\s*Vialidad|\n|$)',
    _FLAGS,
)
_RE_NOMBRE_VIALIDAD = re.compile(
    r'Nombre\s*de\s*Vialidad\s*:\s*'
    r'(.+?)'
    r'(?=\s*N[uú]mero\s*Exterior\s*:|\s*N[uú]mero\s*Interior\s*:'
    r'|\s*Nombre\s*de\s*la\s*Colonia\s*:|\n|$)',
    _FLAGS,
)
_RE_NUM_EXT = re.compile(r'N[uú]mero\s*Exterior\s*:\s*(\S+)', _FLAGS)
_RE_NUM_INT = re.compile(
    r'N[uú]mero\s*Interior\s*:\s*'
    r'([\s\S]*?)'
    r'(?=\s*Nombre\s*de\s*la\s*Colonia\s*:|\Z)',
    _FLAGS,
)
_RE_COLONIA = re.compile(
    r'Nombre\s*de\s*la\s*Colonia\s*:\s*'
    r'([\s\S]+?)'
    r'(?=\s*Nombre\s*de\s*la\s*Localidad\s*:|\s*Nombre\s*del\s*Municipio|\Z)',
    _FLAGS,
)
_RE_LOCALIDAD = re.compile(
    r'Nombre\s*de\s*la\s*Localidad\s*:\s*'
    r'([\s\S]+?)'
    r'(?=\s*Nombre\s*del\s*Municipio\s*(?:o\s*Demarcaci[oó]n\s*Territorial)?\s*:|\Z)',
    _FLAGS,
)
_RE_MUNICIPIO = re.compile(
    r'Nombre\s*del\s*Municipio\s*(?:o\s*Demarcaci[oó]n\s*Territorial)?\s*:\s*'
    r'([\s\S]+?)'
    r'(?=\s*Nombre\s*de\s*la\s*Entidad\s*Federativa\s*:|\Z)',
    _FLAGS,
)
_RE_ESTADO = re.compile(
    r'Nombre\s*de\s*la\s*Entidad\s*Federativa\s*:\s*'
    r'([\s\S]+?)'
    r'(?=\s*Entre\s*Calle\s*:|\s*Y\s*Calle\s*:|\s*Correo\s*Electr|\Z)',
    _FLAGS,
)
_RE_CP = re.compile(r'C[oó]digo\s*Postal\s*:\s*(\d{5})', _FLAGS)
_RE_EMAIL = re.compile(
    r'Correo\s*Electr[oó]nico\s*:\s*([^\s\n\t]+@[^\s\n\t]+)',
    _FLAGS,
)

# Líneas que indican inicio de otra etiqueta (valor pegado al siguiente campo)
_NEXT_LABEL_LINE = re.compile(
    r'^(Nombre|N[uú]mero|C[oó]digo|Entre|Y\s+Calle|Correo|Tipo\s+de)',
    _FLAGS,
)


def _clean(value):
    if not value:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def _normalize_pdf_labels(text: str) -> str:
    """Une etiquetas del SAT que el PDF partió en varias líneas."""
    if not text:
        return text
    normalized = text
    for pattern, replacement in _LABEL_JOIN_PATTERNS:
        normalized = re.sub(pattern, replacement, normalized, flags=_FLAGS)
    return normalized


def _clean_multiline_value(raw: str) -> str:
    """Valor en una o varias líneas; descarta líneas que son otra etiqueta."""
    if not raw:
        return ''
    lines = []
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        if _NEXT_LABEL_LINE.match(line):
            break
        if ':' in line and _NEXT_LABEL_LINE.search(line.split(':', 1)[0]):
            break
        lines.append(line)
    return _clean(' '.join(lines))


def _regex_first(pattern, text):
    match = pattern.search(text or '')
    if not match:
        return ''
    return _clean_multiline_value(match.group(1))


def _extract_interior_pdf(text: str) -> str:
    """
    Número interior del PDF: multilínea y conservando espacios.
    No reutiliza _regex_first (cortaba en el primer salto de línea).
    """
    if not text:
        return ''
    match = _RE_NUM_INT.search(text)
    if not match:
        return ''
    raw = match.group(1)
    parts = []
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        if _NEXT_LABEL_LINE.match(line):
            break
        if line.lower().startswith('nombre de la colonia'):
            break
        parts.append(line)
    return _clean(' '.join(parts))


def extract_address_from_pdf_text(text: str) -> dict:
    """Parsea domicilio del bloque de texto extraído del PDF de la constancia."""
    if not text:
        return {}

    normalized = _normalize_pdf_labels(text)
    flat = re.sub(r'[ \t]+', ' ', normalized)
    flat = re.sub(r'\s*\n\s*', '\n', flat)

    def _pick(pattern):
        return _regex_first(pattern, flat) or _regex_first(pattern, normalized)

    nombre = sanitize_nombre_vialidad(_pick(_RE_NOMBRE_VIALIDAD))
    estado = _pick(_RE_ESTADO)
    if estado:
        estado = format_geo_title(estado)

    return {
        '_tipo_vialidad': _pick(_RE_TIPO_VIALIDAD),
        '_nombre_vialidad': nombre,
        '_num_ext': normalize_exterior_number(_pick(_RE_NUM_EXT)),
        '_num_int': normalize_interior_number(
            _extract_interior_pdf(normalized) or _extract_interior_pdf(flat)
        ),
        '_colonia': format_geo_title(_pick(_RE_COLONIA)),
        '_localidad': format_geo_title(_pick(_RE_LOCALIDAD)),
        '_municipio': format_geo_title(_pick(_RE_MUNICIPIO)),
        '_estado': estado,
        'zip': _pick(_RE_CP),
        'email': _pick(_RE_EMAIL).lower(),
    }
