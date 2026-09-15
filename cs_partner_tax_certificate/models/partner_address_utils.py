# -*- coding: utf-8 -*-
"""Mapeo domicilio SAT → campos separados de res.partner (sin extracción HTML/PDF)."""

import re
import unicodedata

from .cs_partner_tax_certificate_parser import _insert_geo_spaces

_FLAGS = re.IGNORECASE | re.UNICODE

_EMPTY_NUMBERS = frozenset({
    '', '-', 'N/A', 'NA', 'S/N', 'SN', 'SIN NUMERO', 'SIN NÚMERO', 'SIN NUM',
})


def _clean(value):
    if not value:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def _normalize_label(label):
    if not label:
        return ''
    text = unicodedata.normalize('NFKD', label)
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text.lower().strip(':').strip()


def format_geo_title(value):
    text = _clean(value)
    if not text:
        return ''
    return _insert_geo_spaces(text).title()


def sanitize_nombre_vialidad(value):
    if not value:
        return ''
    text = _clean(value)
    for sep in (
        r'\s*N[uú]mero\s*Exterior\s*:',
        r'\s*N[uú]mero\s*Interior\s*:',
        r'\s*Nombre\s*de\s*la\s*Colonia\s*:',
    ):
        text = re.split(sep, text, maxsplit=1, flags=_FLAGS)[0].strip()
    return format_geo_title(text)


def nombre_vialidad_needs_fix(value):
    if not value:
        return True
    low = _normalize_label(value)
    markers = (
        'numero exterior', 'numero interior', 'nombre de la colonia',
        'nombre del municipio', 'entidad federativa',
    )
    return any(marker in low for marker in markers)


def normalize_exterior_number(value):
    text = _clean(value).upper()
    if text in _EMPTY_NUMBERS:
        return ''
    return _clean(value)


def _should_merge_spaced_letters(text: str) -> bool:
    """Solo si el PDF trajo casi todo en letras sueltas (D E P T O), no palabras normales."""
    tokens = text.split()
    if len(tokens) < 3:
        return False
    single = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
    return single >= len(tokens) * 0.5


def _merge_pdf_spaced_letters(text: str) -> str:
    """
    PDF a veces extrae ``D E P T O 5 A`` (letra por letra).
    Une solo bloques de letras sueltas; conserva espacios entre palabras/números.
    """
    if not _should_merge_spaced_letters(text):
        return text
    tokens = text.split()
    merged = []
    buf = []
    for tok in tokens:
        if len(tok) == 1 and tok.isalpha():
            buf.append(tok)
        else:
            if buf:
                merged.append(''.join(buf))
                buf = []
            merged.append(tok)
    if buf:
        merged.append(''.join(buf))
    return ' '.join(merged)


def sanitize_interior_value(value):
    """
    Número interior (PDF o SAT): conserva espacios; nunca usa format_geo_title.

    format_geo_title / _collapse_spaced_allcaps_pdf unían ``DEPTO 5 A`` en ``DEPTO5A``.
    """
    text = _clean(value)
    if not text:
        return ''
    for sep in (
        r'\s*C[oó]digo\s*Postal\s*:',
        r'\s*CP\s*:',
        r'\s*Correo\s*Electr',
        r'\s*N[uú]mero\s*Exterior\s*:',
        r'\s*Nombre\s*de\s*la\s*Colonia\s*:',
    ):
        text = re.split(sep, text, maxsplit=1, flags=_FLAGS)[0].strip()

    if _should_merge_spaced_letters(text):
        text = _merge_pdf_spaced_letters(text)
    elif ' ' not in text and re.search(r'[A-ZÁÉÍÓÚÑ]', text, _FLAGS) and re.search(r'\d', text):
        text = re.sub(r'([A-ZÁÉÍÓÚÑ]{2,})(\d+)', r'\1 \2', text, flags=_FLAGS)
        text = re.sub(r'(\d+)([A-ZÁÉÍÓÚÑ])', r'\1 \2', text, flags=_FLAGS)

    return _clean(text)


# Alias usado por el parser SAT
sanitize_interior_sat = sanitize_interior_value


def normalize_interior_number(value, *, from_sat=False):
    text = _clean(value)
    if text.upper() in _EMPTY_NUMBERS:
        return ''
    return sanitize_interior_value(text)


def resolve_locality(env, locality_name, state_id=False):
    name = _clean(locality_name)
    if not name or 'locality_id' not in env['res.partner']._fields:
        return env['res.locality']
    domain = []
    if state_id:
        domain.append(('state_id', '=', state_id))
    locality = env['res.locality'].search(
        domain + [('name', '=ilike', name)],
        limit=1,
    )
    if locality:
        return locality
    return env['res.locality'].search(
        domain + [('name', 'ilike', name)],
        limit=1,
    )


def resolve_mx_state(env, state_name):
    name = _clean(state_name)
    if not name:
        return env['res.country.state']
    domain = [('country_id.code', '=', 'MX')]
    state = env['res.country.state'].search(
        domain + [('name', '=ilike', name)],
        limit=1,
    )
    if state:
        return state
    return env['res.country.state'].search(
        domain + [('name', 'ilike', name)],
        limit=1,
    )


def address_snapshot_from_partner(partner):
    """Valores actuales del contacto en campos separados."""
    colony = ''
    if 'colony' in partner._fields:
        colony = partner.colony or ''
    if not colony:
        colony = partner.street2 or ''
    locality = ''
    if 'locality' in partner._fields:
        locality = partner.locality or ''
    if not locality and 'locality_id' in partner._fields and partner.locality_id:
        locality = partner.locality_id.name or ''
    return {
        'street_name': _clean(getattr(partner, 'street_name', None) or ''),
        'street_number': _clean(getattr(partner, 'street_number', None) or ''),
        'street_number2': _clean(getattr(partner, 'street_number2', None) or ''),
        'colony': _clean(colony),
        'locality': _clean(locality),
        'city': _clean(partner.city or ''),
        'state': _clean(partner.state_id.name if partner.state_id else ''),
        'zip': _clean(partner.zip or ''),
        'email': _clean(partner.email or ''),
    }


def address_snapshot_from_sat_data(env, data):
    """Valores que se escribirían desde datos SAT (sin unir campos)."""
    vals = partner_address_vals_from_sat(env, data)
    state_name = _clean(data.get('_estado') or data.get('state', ''))
    if vals.get('state_id'):
        state_rec = env['res.country.state'].browse(vals['state_id'])
        state_name = state_rec.name or state_name
    colony = vals.get('colony') or vals.get('street2') or ''
    return {
        'street_name': _clean(vals.get('street_name', '')),
        'street_number': _clean(vals.get('street_number', '')),
        'street_number2': _clean(vals.get('street_number2', '')),
        'colony': _clean(colony),
        'locality': _clean(data.get('_localidad') or data.get('locality', '')),
        'city': _clean(vals.get('city', '')),
        'state': state_name,
        'zip': _clean(vals.get('zip', '')),
        'email': _clean(vals.get('email', '')),
    }


def partner_address_vals_from_sat(env, data: dict) -> dict:
    """
    Mapea domicilio SAT a campos del contacto (cs_cfdi / base_address_extended):

    - Nombre de vialidad → street_name (Calle)
    - Número exterior → street_number (Casa #)
    - Número interior → street_number2 (Puerta #)
    - Colonia → colony (o street2 si no existe colony)
    - Nombre de la localidad → locality / locality_id (si existe en el contacto)
    - Municipio/delegación → city (solo _municipio, no la localidad)
    - Entidad federativa → state_id
    - CP → zip
    - Correo → email
    """
    data = dict(data or {})
    pfields = env['res.partner']._fields
    vals = {}

    nombre = sanitize_nombre_vialidad(
        data.get('_nombre_vialidad') or data.get('street_name', '')
    )
    num_ext = normalize_exterior_number(
        data.get('_num_ext') or data.get('street_number', '')
    )
    num_int = normalize_interior_number(
        data.get('_num_int') or data.get('street_number2', '')
    )
    colonia = format_geo_title(data.get('_colonia') or data.get('colony', ''))
    localidad = format_geo_title(data.get('_localidad') or data.get('locality', ''))
    municipio = format_geo_title(data.get('_municipio') or data.get('city', ''))
    estado = data.get('_estado') or data.get('state', '')
    zip_code = _clean(data.get('zip', ''))
    email = _clean(data.get('email', '')).lower()

    if 'street_name' in pfields:
        if nombre:
            vals['street_name'] = nombre
        if num_ext:
            vals['street_number'] = num_ext
        if num_int:
            vals['street_number2'] = num_int
    else:
        parts = [p for p in (nombre, f'No. {num_ext}' if num_ext else '', f'Int. {num_int}' if num_int else '') if p]
        if parts:
            vals['street'] = ' '.join(parts)

    if 'colony' in pfields:
        if colonia:
            vals['colony'] = colonia
    elif colonia:
        vals['street2'] = colonia

    state = resolve_mx_state(env, estado)
    if state:
        vals['state_id'] = state.id

    if localidad and 'locality_id' in pfields:
        loc_rec = resolve_locality(env, localidad, state.id if state else False)
        if loc_rec:
            vals['locality_id'] = loc_rec.id

    if municipio:
        vals['city'] = municipio
    if zip_code:
        vals['zip'] = zip_code
    if email and '@' in email:
        vals['email'] = email

    mx = env.ref('base.mx', raise_if_not_found=False)
    if mx:
        vals['country_id'] = mx.id

    return vals


def finalize_sat_address_data(result: dict) -> dict:
    """Compatibilidad: ya no fusiona todo en ``street``; deja componentes separados."""
    return result
