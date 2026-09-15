# -*- coding: utf-8 -*-
"""Extracción de regímenes fiscales desde HTML del portal SAT (SIAT). Solo URL."""

import re
import unicodedata

from .fiscal_regime_utils import FISCAL_REGIME_SAT_SELECTION

_FLAGS = re.IGNORECASE | re.UNICODE

# Fechas SAT: 01/01/2022 o 01-01-2022
_FECHA_RE = re.compile(r'\d{2}[-/]\d{2}[-/]\d{4}')

_RE_FECHA_ALTA_IN_VALUE = re.compile(
    r'\s*Fecha\s+de\s+(?:alta|inicio|baja)\s*:.*$',
    _FLAGS,
)

_RE_REGIME_LABEL_ONLY = re.compile(
    r'^(regimen|régimen|regimenes)(\s+fiscal|\s+fiscales)?\s*:?\s*$',
    _FLAGS,
)

_REGIME_HINTS = (
    'personas', 'ley', 'moral', 'fisic', 'físic', 'sueldos', 'arrendamiento',
    'simplificado', 'confianza', 'incorporacion', 'incorporación', 'coordinado',
    'resico', 'general', 'enajenacion', 'enajenación', 'dividendos', 'intereses',
    'agrícola', 'agricola', 'ganader', 'plataforma', 'hidrocarburo', 'obligaciones',
    'asimilados', 'cooperativa', 'consolidacion', 'consolidación', 'premios',
    'extranjero', 'preferente', 'multinacional', 'bolsa',
)

_EXCLUDE_MARKERS = (
    'domicilio', 'vialidad', 'colonia', 'municipio', 'entidad federativa',
    'codigo postal', 'correo electronico', 'rfc', 'curp', 'apellido',
    'razon social', 'razón social', 'denominacion', 'denominación',
    'numero exterior', 'número exterior', 'nombre de la', 'nombre de vialidad',
    'obligaciones:', 'estatus', 'padron', 'padrón', 'capital social',
)


def _normalize_label(label):
    if not label:
        return ''
    text = unicodedata.normalize('NFKD', label)
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text.lower().strip(':').strip()


def _clean(value):
    if not value:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def _is_regime_label(text: str) -> bool:
    if not text:
        return False
    if _RE_REGIME_LABEL_ONLY.match(text.strip()):
        return True
    label_l = _normalize_label(text.rstrip(':'))
    return label_l in ('regimen', 'regimenes', 'regimen fiscal', 'regimenes fiscales')


def _is_fecha_label(text: str) -> bool:
    label_l = _normalize_label(text.rstrip(':'))
    return (
        label_l.startswith('fecha de')
        or label_l in ('fecha', 'fecha alta', 'fecha de alta', 'fecha de inicio', 'fecha de baja')
    )


def _is_pure_fecha(text: str) -> bool:
    t = _clean(text)
    if not t:
        return False
    return bool(_FECHA_RE.fullmatch(t) or (len(t) <= 14 and _FECHA_RE.search(t)))


def _clean_regime_value(text: str) -> str:
    """Solo el nombre del régimen; sin Fecha de alta ni fechas pegadas."""
    t = _clean(text)
    if not t or _is_fecha_label(t) or _is_pure_fecha(t):
        return ''
    t = _RE_FECHA_ALTA_IN_VALUE.sub('', t)
    t = re.split(r'\bFecha\s+de\s+(?:alta|inicio|baja)\b', t, maxsplit=1, flags=_FLAGS)[0]
    t = _FECHA_RE.sub('', t)
    t = re.sub(r'^\d{3}\s*[-–—]?\s*', '', t)
    return _clean(t)


def _matches_catalog(text: str) -> bool:
    low = text.lower()
    for _code, desc in FISCAL_REGIME_SAT_SELECTION:
        words = [w for w in desc.lower().split() if len(w) > 4]
        if sum(1 for w in words if w in low) >= 2:
            return True
    return False


def _looks_like_regime_name(text: str) -> bool:
    t = _clean_regime_value(text)
    if not t or len(t) < 5 or len(t) > 280:
        return False
    if _is_regime_label(t):
        return False
    low = t.lower()
    if any(x in low for x in _EXCLUDE_MARKERS):
        return False
    if _matches_catalog(t) or any(h in low for h in _REGIME_HINTS):
        return True
    return len(t) > 10 and 'fecha de' not in low


def _add_regime(regimenes: list, seen: set, name: str) -> None:
    name = _clean_regime_value(name)
    if not name or not _looks_like_regime_name(name):
        return
    key = name.lower()
    if key in seen:
        return
    seen.add(key)
    regimenes.append(name)


def _parse_label_value_pair(regimenes: list, seen: set, label: str, value: str) -> None:
    if _is_fecha_label(label):
        return
    if _is_regime_label(label):
        _add_regime(regimenes, seen, value)


def _parse_siat_regime_lines(regimenes: list, seen: set, text: str) -> None:
    """
    Formato SIAT habitual::

        Régimen:    Régimen Simplificado de Confianza
        Fecha de alta:    01-01-2022
    """
    lines = [ln.strip() for ln in (text or '').splitlines()]
    for i, line in enumerate(lines):
        if not line or ':' not in line:
            continue
        label, _, val = line.partition(':')
        label, val = label.strip(), val.strip()
        if _is_fecha_label(label):
            continue
        if _is_regime_label(label):
            if val:
                _add_regime(regimenes, seen, val)
            elif i + 1 < len(lines):
                nxt = lines[i + 1]
                if not _is_fecha_label(nxt) and ':' not in nxt:
                    _add_regime(regimenes, seen, nxt)


def _parse_regime_table_pairs(soup, regimenes: list, seen: set) -> None:
    """Filas tabla: celda etiqueta | celda valor."""
    for row in soup.find_all('tr'):
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            text = cells[0].get_text(strip=True) if cells else ''
            if text and ':' in text:
                label, _, val = text.partition(':')
                _parse_label_value_pair(regimenes, seen, label, val)
            continue
        left = cells[0].get_text(strip=True)
        right = cells[1].get_text(strip=True)
        if ':' in left and not right:
            label, _, val = left.partition(':')
            _parse_label_value_pair(regimenes, seen, label.strip(), val.strip())
            continue
        _parse_label_value_pair(regimenes, seen, left, right)


def _parse_regime_catalog_fallback(soup, regimenes: list, seen: set) -> None:
    page = soup.get_text('\n', strip=True).lower()
    for _code, desc in FISCAL_REGIME_SAT_SELECTION:
        if desc.lower() in page:
            _add_regime(regimenes, seen, desc)


def parse_regimes_from_html(soup) -> list:
    """
    Regímenes del HTML SIAT.

    Prioridad: par ``Régimen:`` + texto en la misma fila/línea.
    Ignora por completo ``Fecha de alta`` y fechas (01-01-2022, etc.).
    """
    regimenes = []
    seen = set()

    page_text = soup.get_text('\n', strip=True)

    _parse_regime_table_pairs(soup, regimenes, seen)
    _parse_siat_regime_lines(regimenes, seen, page_text)

    if not regimenes:
        _parse_regime_catalog_fallback(soup, regimenes, seen)

    return regimenes
