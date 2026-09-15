# -*- coding: utf-8 -*-
"""Extracción de domicilio y regímenes desde HTML del portal SAT (SIAT). Solo URL."""

import re
import unicodedata

from .partner_address_utils import (
    format_geo_title,
    normalize_exterior_number,
    normalize_interior_number,
    sanitize_interior_value,
    sanitize_nombre_vialidad,
    nombre_vialidad_needs_fix,
)

_FLAGS = re.IGNORECASE | re.UNICODE

# Etiquetas exactas del portal SIAT (constancia URL; normalizadas sin acentos)
_ADDRESS_LABELS = {
    'tipo de vialidad': '_tipo_vialidad',
    'nombre de vialidad': '_nombre_vialidad',
    'numero exterior': '_num_ext',
    'numero interior': '_num_int',
    'nombre de la colonia': '_colonia',
    'colonia': '_colonia',
    'nombre de la localidad': '_localidad',
    'localidad': '_localidad',
    'nombre del municipio o demarcacion territorial': '_municipio',
    'nombre del municipio': '_municipio',
    'municipio o delegacion': '_municipio',
    'municipio o demarcacion territorial': '_municipio',
    'nombre de la entidad federativa': '_estado',
    'entidad federativa': '_estado',
    'codigo postal': 'zip',
    'cp': 'zip',
    'c.p': 'zip',
    'correo electronico': 'email',
}

# Formato corto del portal (una línea por campo: "Colonia:\tVALOR")
_INLINE_MARKERS = (
    'Entidad Federativa', 'Municipio o delegación', 'Municipio o delegacion',
    'Nombre de la Entidad Federativa', 'Nombre del Municipio',
    'Colonia', 'Nombre de la Colonia', 'Nombre de la Localidad', 'Localidad',
    'Tipo de Vialidad', 'Nombre de Vialidad', 'Nombre de la Vialidad',
    'Número Exterior', 'Numero Exterior', 'Número Interior', 'Numero Interior',
    'Código Postal', 'Codigo Postal', 'CP', 'Correo Electrónico', 'Correo Electronico',
)

_RE_EMBEDDED_LABEL = re.compile(
    r'(?:Nombre\s+de\s+(?:la\s+)?(?:vialidad|colonia|localidad)|'
    r'N[uú]mero\s+(?:Exterior|Interior)|'
    r'(?:Municipio|Entidad\s+Federativa|Colonia|Localidad)\s*:|'
    r'CP\s*:|C[oó]digo\s+Postal)',
    _FLAGS,
)

_RE_SIAT_VIALIDAD = re.compile(
    r'Nombre\s+de\s+(?:la\s+)?vialidad\s*:\s*([^\n\t]+?)(?=\s*(?:N[uú]mero|CP|Correo)\s*:|$)',
    _FLAGS,
)

# Etiqueta sola en una línea/fila (valor en la siguiente)
_RE_LABEL_ONLY = re.compile(
    r'^(Entidad\s+Federativa|Municipio\s+o\s+delegaci[oó]n|Colonia|Localidad|'
    r'Tipo\s+de\s+vialidad|Nombre\s+de\s+(?:la\s+)?vialidad|'
    r'N[uú]mero\s+(?:Exterior|Interior)|CP|C[oó]digo\s+Postal|Correo\s+electr[oó]nico)\s*:?\s*$',
    _FLAGS,
)

_INVALID_INTERIOR_MARKERS = (
    'codigo postal', 'c.p.', 'cp:', 'nombre de', 'entidad federativa',
    'municipio', 'colonia', 'localidad', 'correo', 'regimen', 'regimenes',
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


def _clean_multiline_value(raw: str) -> str:
    if not raw:
        return ''
    lines = []
    for line in str(raw).split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.match(
            r'^(Nombre|N[uú]mero|C[oó]digo|Entre|Y\s+Calle|Correo|Tipo\s+de)',
            line,
            _FLAGS,
        ):
            break
        lines.append(line)
    return _clean(' '.join(lines))


def _resolve_address_label(label_l: str):
    """Solo etiquetas de domicilio; evita confundir con otros campos del HTML."""
    if not label_l:
        return None
    if label_l in _ADDRESS_LABELS:
        return _ADDRESS_LABELS[label_l]
    if 'nombre de vialidad' in label_l:
        return '_nombre_vialidad'
    if label_l.endswith('nom de vialidad'):
        return '_nombre_vialidad'
    if 'numero exterior' in label_l or 'número exterior' in label_l.replace('ú', 'u'):
        return '_num_ext'
    if 'numero interior' in label_l or 'número interior' in label_l.replace('ú', 'u'):
        return '_num_int'
    if 'nombre de la colonia' in label_l or label_l == 'colonia':
        return '_colonia'
    if 'nombre de la localidad' in label_l and 'colonia' not in label_l:
        return '_localidad'
    if (
        ('municipio' in label_l or 'demarcacion territorial' in label_l)
        and 'entidad' not in label_l
    ):
        return '_municipio'
    if 'entidad federativa' in label_l or label_l == 'entidad federativa':
        return '_estado'
    if label_l in ('cp', 'c.p', 'c.p.') or 'codigo postal' in label_l:
        return 'zip'
    if label_l in ('email', 'e-mail', 'correo') or 'correo electr' in label_l:
        return 'email'
    if label_l.startswith('municipio o deleg'):
        return '_municipio'
    return None


def _sanitize_estado_value(value: str) -> str:
    text = _clean(value)
    if not text:
        return ''
    low = text.lower()
    for marker in (
        'entre calle', 'y calle', 'codigo postal', 'correo electronico',
        'regimen', 'nombre de', 'numero exterior', 'numero interior',
    ):
        if marker in low:
            text = re.split(marker, text, maxsplit=1, flags=_FLAGS)[0].strip()
    return format_geo_title(text)


def _is_valid_interior(value: str) -> bool:
    text = _clean(value)
    if not text or text.upper() in ('-', 'N/A', 'NA', 'S/N', 'SN'):
        return False
    low = text.lower()
    if any(m in low for m in _INVALID_INTERIOR_MARKERS):
        return False
    if re.search(r'\b\d{5}\b', text):
        return False
    if ':' in text and re.search(r'(codigo|postal|colonia|municipio)', low):
        return False
    return True


def _assign_address_field(result: dict, field: str, value: str) -> None:
    if field in ('_colonia', '_localidad', '_municipio', '_estado', '_nombre_vialidad'):
        value = _clean_multiline_value(value)
    else:
        value = _clean(value)
    if not value or value in ('-', 'N/A', 'n/a'):
        return

    if field == '_nombre_vialidad':
        cleaned = sanitize_nombre_vialidad(value)
        if not cleaned:
            return
        current = result.get('_nombre_vialidad', '')
        if nombre_vialidad_needs_fix(current) or not current:
            result['_nombre_vialidad'] = cleaned
        return

    if field == '_num_ext':
        num = normalize_exterior_number(value)
        if num:
            result.setdefault('_num_ext', num)
        return

    if field == '_num_int':
        value = sanitize_interior_value(value) or value
        if _is_valid_interior(value):
            num = normalize_interior_number(value)
            if num:
                result.setdefault('_num_int', num)
        return

    if field == '_estado':
        estado = _sanitize_estado_value(value)
        if estado:
            result.setdefault('_estado', estado)
        return

    if field == 'zip':
        cp = re.search(r'\b\d{5}\b', value)
        if cp:
            result.setdefault('zip', cp.group(0))
        return

    if field == 'email':
        email = value.lower().strip()
        if '@' in email:
            result.setdefault('email', email)
        return

    if field in ('_colonia', '_localidad', '_municipio', '_tipo_vialidad'):
        formatted = format_geo_title(value)
        if formatted:
            result.setdefault(field, formatted)
        return


def _value_has_embedded_labels(value: str) -> bool:
    return bool(value and _RE_EMBEDDED_LABEL.search(value))


def _map_address_pair(result: dict, label: str, value: str) -> None:
    label_l = _normalize_label(label)
    field = _resolve_address_label(label_l)

    if value and _value_has_embedded_labels(value):
        # Ej.: Tipo de vialidad vacío y el valor trae "Nombre de la vialidad: OLMOS"
        _parse_inline_address_block(result, value)
        if field and field != '_tipo_vialidad':
            cut = _RE_EMBEDDED_LABEL.split(value)[0].strip(' :,')
            if cut:
                _assign_address_field(result, field, cut)
        return

    if not field:
        return
    _assign_address_field(result, field, value)


def _parse_inline_address_block(result: dict, block: str) -> None:
    if not block or ':' not in block:
        return
    pattern = '|'.join(re.escape(m) for m in _INLINE_MARKERS)
    parts = re.split(rf'(?={pattern})', block, flags=re.IGNORECASE)
    for part in parts:
        part = part.strip()
        if ':' not in part:
            continue
        label, _, value = part.partition(':')
        _map_address_pair(result, label, value)


def _is_address_text(text: str) -> bool:
    low = (text or '').lower()
    return any(marker in low for marker in (
        'nombre de la vialidad', 'nombre de vialidad',
        'entidad federativa', 'municipio o delegacion', 'municipio o delegación',
        'colonia', 'numero exterior', 'número exterior', 'cp:', 'codigo postal',
    ))


def _iter_address_text_blocks(soup):
    """Bloques de texto del SIAT con domicilio (formato línea a línea)."""
    seen = set()
    for table in soup.find_all('table'):
        txt = table.get_text('\n', strip=True)
        if _is_address_text(txt) and txt not in seen:
            seen.add(txt)
            yield txt
    keywords = (
        'datos del domicilio', 'domicilio registrado', 'domicilio fiscal',
        'ubicacion del domicilio',
    )
    for tag in soup.find_all(string=re.compile('|'.join(keywords), _FLAGS)):
        parent = tag.find_parent(['table', 'div', 'section', 'fieldset'])
        if not parent:
            continue
        txt = parent.get_text('\n', strip=True)
        if txt and txt not in seen:
            seen.add(txt)
            yield txt


def _parse_plain_label_lines(result: dict, text: str) -> None:
    """Formato SIAT: 'Etiqueta: valor' o etiqueta en una línea y valor en la siguiente."""
    if not text:
        return
    lines = [ln.strip() for ln in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue
        if ':' in line:
            idx = line.find(':')
            label = line[:idx].strip()
            value = line[idx + 1:].strip()
            if not value and i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt and ':' not in nxt and not _RE_LABEL_ONLY.match(nxt):
                    value = nxt
                    i += 1
            _map_address_pair(result, label, value)
        elif _RE_LABEL_ONLY.match(line):
            label = line
            value = ''
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt and ':' not in nxt and not _RE_LABEL_ONLY.match(nxt):
                    value = nxt
                    i += 1
            _map_address_pair(result, label, value)
        i += 1


def _parse_stacked_table_rows(soup, result: dict) -> None:
    """Filas con etiqueta en un renglón y valor en el siguiente (muy común en SIAT)."""
    rows = soup.find_all('tr')
    for idx, row in enumerate(rows):
        cells = row.find_all(['td', 'th'])
        texts = [c.get_text(strip=True) for c in cells]
        if not texts:
            continue

        if len(texts) == 1:
            text = texts[0]
            if ':' in text:
                label, _, val = text.partition(':')
                label, val = label.strip(), val.strip()
                field = _resolve_address_label(_normalize_label(label))
                if val:
                    _map_address_pair(result, label, val)
                elif field:
                    val = _value_from_following_rows(rows, idx)
                    if val:
                        _assign_address_field(result, field, val)
            elif _RE_LABEL_ONLY.match(text):
                field = _resolve_address_label(_normalize_label(text))
                if field:
                    val = _value_from_following_rows(rows, idx)
                    if val:
                        _assign_address_field(result, field, val)
            continue

        if len(texts) >= 2:
            left, right = texts[0], texts[1]
            if _resolve_address_label(_normalize_label(left.rstrip(':'))) and not _resolve_address_label(
                _normalize_label(right.rstrip(':'))
            ):
                _map_address_pair(result, left, right)


def _value_from_following_rows(rows, start_idx: int) -> str:
    for row in rows[start_idx + 1:start_idx + 4]:
        texts = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
        if not texts:
            continue
        if len(texts) == 1:
            cand = texts[0]
            if cand and ':' not in cand and not _RE_LABEL_ONLY.match(cand):
                return cand
        if len(texts) >= 2 and texts[1]:
            if not _resolve_address_label(_normalize_label(texts[0].rstrip(':'))):
                return texts[1]
    return ''


def _parse_label_element_proximity(soup, result: dict) -> None:
    """Busca la etiqueta en el DOM y toma el valor del hermano o fila siguiente."""
    for tag in soup.find_all(['td', 'th', 'span', 'label', 'strong', 'b']):
        raw = tag.get_text(strip=True)
        if not raw or len(raw) > 120:
            continue

        if ':' in raw:
            label_part, _, val_part = raw.partition(':')
            label_part, val_part = label_part.strip(), val_part.strip()
            field = _resolve_address_label(_normalize_label(label_part))
            if field and val_part:
                _assign_address_field(result, field, val_part)
                continue
            elif not field:
                continue
        else:
            norm = _normalize_label(raw.rstrip(':'))
            field = _resolve_address_label(norm)
            if not field:
                continue

        value = ''
        sib = tag.find_next_sibling(['td', 'span', 'div', 'p'])
        if sib:
            value = sib.get_text(strip=True)

        if not value:
            parent_cell = tag if tag.name in ('td', 'th') else tag.find_parent(['td', 'th'])
            if parent_cell:
                row = parent_cell.find_parent('tr')
                if row:
                    for cell in row.find_all(['td', 'th']):
                        if cell is parent_cell:
                            continue
                        cell_text = cell.get_text(strip=True)
                        if cell_text and not _resolve_address_label(_normalize_label(cell_text.rstrip(':'))):
                            value = cell_text
                            break
                    if not value:
                        nxt_row = row.find_next_sibling('tr')
                        if nxt_row:
                            nxt_cells = nxt_row.find_all(['td', 'th'])
                            if len(nxt_cells) == 1:
                                value = nxt_cells[0].get_text(strip=True)

        if not value or _resolve_address_label(_normalize_label(value.rstrip(':'))):
            continue
        _assign_address_field(result, field, value)


def _apply_regex_fallbacks(result: dict, text: str) -> None:
    if not result.get('_nombre_vialidad'):
        match = _RE_SIAT_VIALIDAD.search(text or '')
        if match:
            _assign_address_field(result, '_nombre_vialidad', match.group(1))
    if not result.get('_nombre_vialidad') and text:
        lines = [ln.strip() for ln in text.splitlines()]
        for i, line in enumerate(lines):
            if not re.search(r'nombre\s+de\s+(?:la\s+)?vialidad', line, _FLAGS):
                continue
            val = line.partition(':')[2].strip() if ':' in line else ''
            if not val and i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt and ':' not in nxt and not _RE_LABEL_ONLY.match(nxt):
                    val = nxt
            if val:
                _assign_address_field(result, '_nombre_vialidad', val)
                break


def parse_address_from_html(soup) -> dict:
    """Solo domicilio desde HTML SAT (tablas, labels, bloque domicilio)."""
    result = {}

    _parse_stacked_table_rows(soup, result)
    _parse_label_element_proximity(soup, result)

    for row in soup.find_all('tr'):
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        cell_texts = [c.get_text(separator=' ', strip=True) for c in cells]
        if len(cells) == 1:
            if _is_address_text(cell_texts[0]):
                _parse_plain_label_lines(result, cell_texts[0])
                _parse_inline_address_block(result, cell_texts[0])
            continue
        if len(cell_texts) >= 4 and len(cell_texts) % 2 == 0:
            for idx in range(0, len(cell_texts), 2):
                _map_address_pair(result, cell_texts[idx], cell_texts[idx + 1])
        elif len(cell_texts) >= 2:
            _map_address_pair(result, cell_texts[0], cell_texts[1])

    for dt in soup.find_all('dt'):
        dd = dt.find_next_sibling('dd')
        if dd:
            _map_address_pair(
                result,
                dt.get_text(strip=True),
                dd.get_text(strip=True),
            )

    for label_tag in soup.find_all('label'):
        sib = label_tag.find_next_sibling(['span', 'div', 'td', 'p'])
        if sib:
            _map_address_pair(
                result,
                label_tag.get_text(strip=True),
                sib.get_text(strip=True),
            )

    page_text_parts = []
    for block in _iter_address_text_blocks(soup):
        _parse_plain_label_lines(result, block)
        _parse_inline_address_block(result, block)
        page_text_parts.append(block)

    page_text = '\n'.join(page_text_parts) or soup.get_text('\n', strip=True)
    _apply_regex_fallbacks(result, page_text)

    return result


def merge_sat_address_into(result: dict, patch: dict) -> None:
    """Fusiona domicilio parseado del HTML SAT sin sobrescribir valores válidos."""
    for key, value in (patch or {}).items():
        if not value:
            continue
        if key == '_nombre_vialidad':
            current = result.get('_nombre_vialidad') or ''
            if nombre_vialidad_needs_fix(current) or not current:
                result['_nombre_vialidad'] = value
            continue
        if key in ('zip', 'email'):
            result.setdefault(key, value)
        elif not result.get(key):
            result[key] = value
