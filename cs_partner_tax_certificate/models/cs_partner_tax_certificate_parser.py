# -*- coding: utf-8 -*-

import base64
import io
import logging
import mimetypes
import re
import unicodedata

from odoo import models, _

from .dependency_utils import (
    is_libzbar_missing_error,
    msg_missing_fitz,
    msg_missing_pypdf2,
    msg_missing_pyzbar,
    msg_pdf_invalid,
    qr_dependency_warning,
)

_logger = logging.getLogger(__name__)

PDF_SIGNATURE = b'%PDF-'
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# ──────────────────────────────────────────────────────────────
# Flags globales para todos los patrones
# ──────────────────────────────────────────────────────────────
_FLAGS = re.IGNORECASE | re.UNICODE

# ──────────────────────────────────────────────────────────────
# RFC
# ──────────────────────────────────────────────────────────────
_RFC_RE = re.compile(
    r'RFC:\s*\t?\s*([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b',
    _FLAGS,
)

# ──────────────────────────────────────────────────────────────
# Nombre / Razón social
# ──────────────────────────────────────────────────────────────

_NOMBRE_HEADER_RE = re.compile(
    r'Registro\s*Federal\s*de\s*Contribuyentes\s*\n'
    r'([^\n]+)'          # línea 1 del nombre
    r'(?:\n([^\n]+))?'  # línea 2 opcional (apellidos desglosados en PF)
    r'\n(?:Nombre|RFC|Nombre\s*\(s\))',
    _FLAGS,
)

# FALLBACK: campo de datos del contribuyente
_NOMBRE_MORAL_INLINE_RE = re.compile(
    r'Denominaci[oó]n\s*/\s*Raz[oó]n\s*Social\s*:\s*([^\n]*)',
    _FLAGS,
)
_NOMBRE_MORAL_MULTILINE_RE = re.compile(
    r'Denominaci[oó]n\s*/\s*Raz[oó]n\s*Social\s*:\s*(.+?)'
    r'(?=\nR[eé]gimen\s*Capital|\nNombre\s*Comercial|\nFecha\s*inicio|\nEstatus)',
    re.DOTALL | _FLAGS,
)

# Persona física (etiquetas del SAT en constancia y portal)
_NOMBRE_PF_RE = re.compile(r'Nombre\s*\(s\)\s*:\s*([^\n]*)', _FLAGS)
_APELLIDO_PATERNO_RE = re.compile(r'Apellido\s*Paterno\s*:\s*([^\n]*)', _FLAGS)
_APELLIDO_MATERNO_RE = re.compile(r'Apellido\s*Materno\s*:\s*([^\n]*)', _FLAGS)
_APELLIDO1_RE = re.compile(r'Primer\s*Apellido\s*:\s*([^\n]*)', _FLAGS)
_APELLIDO2_RE = re.compile(r'Segundo\s*Apellido\s*:\s*([^\n]*)', _FLAGS)

# ──────────────────────────────────────────────────────────────
# Domicilio
# ──────────────────────────────────────────────────────────────

_CP_RE = re.compile(r'C[oó]digo\s*Postal\s*:[ \t]*(\d{5})', _FLAGS)

# ──────────────────────────────────────────────────────────────
# Regímenes fiscales
# ──────────────────────────────────────────────────────────────
_REGIMENES_BLOQUE_RE = re.compile(
    r'Reg[ií]menes?\s*:[ \t]*\n.+?\n(.+?)'
    r'(?=\nObligaciones\s*:|\nSus\s*datos\s*personales|\Z)',
    re.DOTALL | _FLAGS,
)
_FECHA_RE = re.compile(r'\d{2}/\d{2}/\d{4}')

# ──────────────────────────────────────────────────────────────
# Mapeo texto → código SAT
# ──────────────────────────────────────────────────────────────
_REGIMEN_MAP = [
    ('601', 'General de Ley Personas Morales'),
    ('603', 'Personas Morales con Fines no Lucrativos'),
    ('605', 'Sueldos y Salarios e Ingresos Asimilados'),
    ('606', 'Arrendamiento'),
    ('607', 'Enajenación o Adquisición de Bienes'),
    ('608', 'Demás ingresos'),
    ('610', 'Residentes en el Extranjero'),
    ('611', 'Dividendos'),
    ('612', 'Personas Físicas con Actividades Empresariales'),
    ('614', 'Ingresos por intereses'),
    ('615', 'Obtención de premios'),
    ('616', 'Sin obligaciones fiscales'),
    ('620', 'Sociedades Cooperativas'),
    ('621', 'Incorporación Fiscal'),
    ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas'),
    ('623', 'Grupos de Sociedades'),
    ('624', 'Coordinados'),
    ('625', 'Plataformas Tecnológicas'),
    ('626', 'Simplificado de Confianza'),
    ('628', 'Hidrocarburos'),
    ('629', 'Regímenes Fiscales Preferentes'),
    ('630', 'Enajenación de acciones en bolsa'),
]


def _best_regime_code(text):
    text_l = text.lower()
    best_code, best_score = None, 0
    for code, keywords in _REGIMEN_MAP:
        words = [w for w in keywords.lower().split() if len(w) > 3]
        score = sum(1 for w in words if w in text_l)
        if score > best_score:
            best_score = score
            best_code = code
    return best_code


# ──────────────────────────────────────────────────────────────
# Utilidades de texto
# ──────────────────────────────────────────────────────────────

def _clean(value):
    """Colapsa espacios/tabuladores y aplica strip."""
    if not value:
        return ''
    text = re.sub(r'[\u00a0\u2000-\u200b]+', ' ', str(value))
    return re.sub(r'[ \t]+', ' ', text).strip()


def _should_merge_spaced_letters_name(text: str) -> bool:
    """PDF SAT: letras sueltas (P E D R O); no confundir con palabras ya formadas."""
    tokens = text.split()
    if len(tokens) < 2:
        return False
    single = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
    return single >= len(tokens) * 0.5


def _merge_pdf_spaced_letters_name(text: str) -> str:
    """
    Une letras sueltas en palabras y conserva el espacio entre palabras/números.
    Ej.: ``P E D R O   P A B L O`` → ``PEDRO PABLO`` (con doble espacio como límite).
    """
    if not _should_merge_spaced_letters_name(text):
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


def _normalize_name_spacing(value):
    """
    Restaura espacios en razón social / nombre tras la extracción del PDF.
    """
    value = _clean(value)
    if not value:
        return ''
    # El SAT a veces separa palabras con dos o más espacios en el PDF.
    if re.search(r' {2,}', value):
        parts = [p.strip() for p in re.split(r' {2,}', value) if p.strip()]
        return ' '.join(_normalize_name_spacing(part) for part in parts)
    value = _merge_pdf_spaced_letters_name(value)
    if ' ' not in value and len(value) >= 10:
        expanded = _expand_fused_geo(value)
        if expanded:
            return expanded
    return value


def _first(pattern, text):
    m = pattern.search(text)
    return _clean(m.group(1)) if m else ''


def _sanitize_name_part(value):
    """Descarta capturas que en realidad son otra etiqueta del PDF."""
    value = _clean(value)
    if not value or value in ('-', 'N/A', 'n/a'):
        return ''
    if value.endswith(':'):
        return ''
    low = value.lower().strip(':').strip()
    if low.startswith((
        'apellido paterno', 'apellido materno', 'primer apellido', 'segundo apellido',
        'nombre (s)', 'nombre(s)', 'denominaci', 'régimen', 'regimen', 'nombre de',
    )):
        return ''
    return _normalize_name_spacing(value)


def _first_label_value(text, pattern):
    """Valor en la misma línea o en la línea inmediata siguiente (PDF SAT)."""
    m = pattern.search(text)
    if not m:
        return ''
    val = _sanitize_name_part(m.group(1))
    if val:
        return val
    tail = text[m.end():]
    m_next = re.match(r'[ \t]*\r?\n[ \t]*([^\n]+)', tail)
    if m_next:
        return _sanitize_name_part(m_next.group(1))
    return ''


def _extract_pf_name_parts(text):
    """Nombre(s) y apellidos desglosados en constancias de persona física."""
    n = _first_label_value(text, _NOMBRE_PF_RE)
    a1 = _first_label_value(text, _APELLIDO_PATERNO_RE) or _first_label_value(text, _APELLIDO1_RE)
    a2 = _first_label_value(text, _APELLIDO_MATERNO_RE) or _first_label_value(text, _APELLIDO2_RE)
    return n, a1, a2


def _build_full_name(nombre, apellido1, apellido2):
    parts = (nombre, apellido1, apellido2)
    return _normalize_name_spacing(' '.join(p for p in parts if p))


def _extract_header_name(text):
    m_hdr = _NOMBRE_HEADER_RE.search(text)
    if not m_hdr:
        return ''
    linea1 = _sanitize_name_part(m_hdr.group(1))
    linea2 = _sanitize_name_part(m_hdr.group(2)) if m_hdr.group(2) else ''
    if linea2 and (
        linea2.lower().startswith('nombre')
        or _RFC_RE.search(linea2)
    ):
        linea2 = ''
    if linea1 and _RFC_RE.search(linea1):
        linea1 = ''
    return _normalize_name_spacing(' '.join(p for p in (linea1, linea2) if p))


def _extract_moral_name(text):
    m = _NOMBRE_MORAL_MULTILINE_RE.search(text)
    if m:
        val = _sanitize_name_part(re.sub(r'[\r\n]+', ' ', m.group(1)))
        if val:
            return val
    return _first_label_value(text, _NOMBRE_MORAL_INLINE_RE)


def _extract_contribuyente_name(text):
    """
    Razón social (moral) o nombre completo (física).
    Prioridad: moral explícita → PF con apellidos → cabecera → campos PF sueltos.
    """
    header_n = _extract_header_name(text)
    moral = _extract_moral_name(text)
    n_pf, ap_pat, ap_mat = _extract_pf_name_parts(text)

    if moral and not (ap_pat or ap_mat):
        return _normalize_name_spacing(moral)

    if ap_pat or ap_mat:
        base = n_pf or header_n
        full = _build_full_name(base, ap_pat, ap_mat)
        if full:
            return full

    if n_pf:
        full = _build_full_name(n_pf, ap_pat, ap_mat)
        if full:
            return full

    if header_n:
        return _normalize_name_spacing(header_n)

    return _normalize_name_spacing(moral) if moral else ''


_PARTICLES_RE = re.compile(
    r'(?<=[A-ZÁÉÍÓÚÜÑ]{2})'
    r'((?:DE(?!RO)(?=[A-ZÁÉÍÓÚÜÑ]{3})|SANTA|SANTO|LAS|LOS|SAN|EL))'
    r'(?=[A-ZÁÉÍÓÚÜÑ]{2})',
    re.IGNORECASE | re.UNICODE,
)

_LAS_LOS_WORD_RE = re.compile(
    r'^(LAS|LOS)([A-ZÁÉÍÓÚÜÑ]{3,})$',
    re.IGNORECASE | re.UNICODE,
)


def _apply_las_los_tokens(segment: str) -> str:

    parts = segment.split()
    out = []
    for p in parts:
        m = _LAS_LOS_WORD_RE.match(p)
        if m:
            out.append('%s %s' % (m.group(1), m.group(2)))
        else:
            out.append(p)
    return ' '.join(out)


def _collapse_spaced_allcaps_pdf(text: str) -> str:

    if not text or ' ' not in text:
        return text
    raw = text.strip()

    upper = raw.upper()
    words = upper.split()
    if len(words) < 2:
        return text
    collapsed = ''.join(words)

    # No colapsar si hay dígitos (número interior, exterior, etc.)
    if any(any(c.isdigit() for c in w) for w in words):
        return text

    short = sum(1 for w in words if len(w) <= 2)
    if len(words) >= 4 and short >= len(words) * 0.45:
        return collapsed

    if len(collapsed) >= 6 and len(words) >= max(5, len(collapsed) // 3):
        letterish = sum(1 for c in collapsed if c.isalpha())
        if letterish >= len(collapsed) * 0.85:
            return collapsed
    return text


def _expand_fused_geo(fused: str) -> str:

    if not fused:
        return fused
    work = re.sub(r'\s+', '', fused).strip().upper()
    if len(work) < 4:
        return fused.strip()
    work = _apply_las_los_tokens(work)
    prev = None
    while prev != work:
        prev = work
        work = _PARTICLES_RE.sub(r' \1 ', work)
        work = re.sub(r' +', ' ', work).strip()
        work = _apply_las_los_tokens(work)
    return work


def _insert_geo_spaces(text: str) -> str:

    if not text:
        return text
    t = _collapse_spaced_allcaps_pdf(text)

    if ' ' not in t:
        return _expand_fused_geo(t)

    parts = t.split()
    out = []
    for p in parts:
        inner = re.sub(r'\s+', '', p)
        if len(inner) >= 8:
            out.append(_expand_fused_geo(inner))
        else:
            out.append(p)
    return ' '.join(out)


# ──────────────────────────────────────────────────────────────
# Modelo
# ──────────────────────────────────────────────────────────────

class CsPartnerTaxCertificateParser(models.AbstractModel):

    _name = 'cs.partner.tax.certificate.parser'
    _description = 'Parser de Constancia de Situación Fiscal (SAT)'

    def parse(self, b64_data: str, filename: str = 'constancia.pdf') -> dict:
        """
        Extrae datos de la Constancia de Situación Fiscal.

        :returns: dict con claves:
            rfc, name, street, street2, city, state, zip,
            fiscal_regime_code, fiscal_regime_text, sat_url, warnings, raw_text, error
        """
        try:
            pdf_bytes = base64.b64decode(b64_data)
        except Exception:
            return {'error': _('El archivo no es base64 válido.')}

        error = self._validate(pdf_bytes, filename)
        if error:
            return {'error': error}

        text, extract_error = self._extract_text(pdf_bytes)
        if extract_error:
            return {'error': extract_error}

        _logger.debug('CIFParser texto (primeros 2000):\n%s', text[:2000])
        result = self._parse_fields(text)
        result['raw_text'] = text
        sat_url, qr_warning = self._extract_qr_url(pdf_bytes)
        result['sat_url'] = sat_url
        if qr_warning:
            existing = (result.get('warnings') or '').strip()
            result['warnings'] = '\n'.join(
                part for part in (existing, qr_warning) if part
            )
        return result

    # ── Validación ───────────────────────────────────────────────

    def _validate(self, pdf_bytes, filename):
        if not filename.lower().endswith('.pdf'):
            return _('Solo se aceptan archivos con extensión .pdf')
        mime, _ = mimetypes.guess_type(filename)
        if mime and mime != 'application/pdf':
            return _('El tipo MIME del archivo no corresponde a un PDF.')
        if not pdf_bytes.startswith(PDF_SIGNATURE):
            return msg_pdf_invalid(_('Falta la firma estándar %PDF-.'))
        if len(pdf_bytes) > MAX_SIZE_BYTES:
            return _('El archivo excede el tamaño máximo de 10 MB.')
        return None

    # ── Extracción de texto ──────────────────────────────────────

    def _extract_text(self, pdf_bytes):
        try:
            import PyPDF2  # noqa: WPS433
        except ImportError:
            return None, msg_missing_pypdf2()
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            pages = [page.extract_text() or '' for page in reader.pages]
            raw = '\n'.join(pages)
            # NFKC: convierte 'o' + combining-accent → 'ó' (NFD→NFC)
            return unicodedata.normalize('NFKC', raw), None
        except PyPDF2.errors.PdfReadError as exc:
            return None, msg_pdf_invalid(str(exc))
        except Exception as exc:  # noqa: BLE001
            _logger.exception('CIFParser: error inesperado')
            return None, _('Error inesperado: %s') % str(exc)

    # ── Parseo de campos ─────────────────────────────────────────

    def _parse_fields(self, text: str) -> dict:
        warnings = []
        result = {}

        # ── RFC ──────────────────────────────────────────────────
        rfc = _first(_RFC_RE, text)
        if rfc:
            result['rfc'] = rfc.upper()
        else:
            warnings.append(_('No se encontró el RFC.'))

        # ── Nombre / Razón social ────────────────────────────────
        nombre = _extract_contribuyente_name(text)
        if nombre:
            result['name'] = nombre
        else:
            warnings.append(_('No se encontró la razón social / nombre.'))

        # ── Código Postal ────────────────────────────────────────
        result['zip'] = _first(_CP_RE, text)
        if not result['zip']:
            warnings.append(_('No se encontró el Código Postal.'))

        # ── Domicilio (solo motor PDF) ───────────────────────────
        from .pdf_address_extract import extract_address_from_pdf_text

        addr = extract_address_from_pdf_text(text)
        result['street_name'] = addr.get('_nombre_vialidad', '')
        result['street_number'] = addr.get('_num_ext', '')
        result['street_number2'] = addr.get('_num_int', '')
        if not result['street_name']:
            warnings.append(_('No se encontró el nombre de la vialidad (calle).'))

        result['colony'] = addr.get('_colonia', '')
        result['street2'] = result['colony']

        result['locality'] = addr.get('_localidad', '')
        if not result['locality']:
            warnings.append(_('No se encontró el nombre de la localidad.'))

        if addr.get('_municipio'):
            result['city'] = addr['_municipio']
        else:
            result['city'] = ''
            warnings.append(_('No se encontró el municipio o delegación.'))

        result['state'] = addr.get('_estado', '')
        if not result['state']:
            warnings.append(_('No se encontró el estado / entidad federativa.'))

        if addr.get('zip') and not result.get('zip'):
            result['zip'] = addr['zip']
        if addr.get('email'):
            result['email'] = addr['email']

        # ── Regímenes fiscales ───────────────────────────────────
        result['fiscal_regime_text'], result['fiscal_regime_code'] = \
            self._parse_regimenes(text, warnings)

        result['warnings'] = '\n'.join(warnings)
        return result

    # ── URL del QR del SAT ───────────────────────────────────────

    def _extract_qr_url(self, pdf_bytes: bytes):
        """
        Renderiza cada página del PDF y decodifica el código QR del SAT.

        Devuelve (url, aviso): url vacía si no hay QR; aviso con mensaje amigable
        si faltan dependencias o no se encontró código QR.
        """
        deps = {'pymupdf': True, 'pyzbar': True, 'libzbar': True}
        try:
            import fitz  # pymupdf
        except ImportError:
            deps['pymupdf'] = False
            _logger.warning('CIFParser: pymupdf (fitz) no está instalado.')
            return '', msg_missing_fitz()

        try:
            from pyzbar.pyzbar import decode as qr_decode
            from PIL import Image
        except ImportError:
            deps['pyzbar'] = False
            _logger.warning('CIFParser: pyzbar o Pillow no están instalados.')
            return '', msg_missing_pyzbar()

        try:
            doc = fitz.open(stream=pdf_bytes, filetype='pdf')
            for page in doc:
                mat = fitz.Matrix(3, 3)
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
                img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                for obj in qr_decode(img):
                    data = obj.data.decode('utf-8', errors='ignore').strip()
                    if data.lower().startswith('http'):
                        _logger.debug('CIFParser QR URL: %s', data)
                        doc.close()
                        return data, None
            doc.close()
        except Exception as exc:
            if is_libzbar_missing_error(exc):
                deps['libzbar'] = False
                _logger.warning('CIFParser: libzbar0 no disponible: %s', exc)
                return '', qr_dependency_warning(deps)
            _logger.exception('CIFParser: error al extraer URL del QR')

        return '', qr_dependency_warning(deps)

    # ── Regímenes ────────────────────────────────────────────────

    def _parse_regimenes(self, text, warnings):
        m = _REGIMENES_BLOQUE_RE.search(text)
        if not m:
            warnings.append(_('No se encontró el bloque de Regímenes.'))
            return '', None

        regimenes = []
        for linea in m.group(1).splitlines():
            sin_fecha = _clean(_FECHA_RE.sub('', linea))
            if sin_fecha:
                regimenes.append(sin_fecha)

        if not regimenes:
            warnings.append(_('No se pudieron extraer los regímenes.'))
            return '', None

        primer = regimenes[0]
        return (' | '.join(regimenes) if len(regimenes) > 1 else primer,
                _best_regime_code(primer))
