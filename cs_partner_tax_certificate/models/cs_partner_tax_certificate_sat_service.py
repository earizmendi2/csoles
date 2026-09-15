# -*- coding: utf-8 -*-
import logging
import os
import re
import ssl
import urllib.parse

from odoo import models, _
from odoo.exceptions import UserError

from .dependency_utils import (
    msg_missing_bs4,
    msg_missing_requests,
    msg_sat_format_changed,
    msg_sat_unavailable,
)
from .partner_address_utils import _normalize_label
from .sat_address_parser import (
    merge_sat_address_into,
    parse_address_from_html,
    _resolve_address_label,
)
from .sat_regime_parser import parse_regimes_from_html

_logger = logging.getLogger(__name__)

_SAT_ALLOWED_HOSTS = {'siat.sat.gob.mx', 'www.siat.sat.gob.mx'}
_REQUEST_TIMEOUT = 20  # segundos

# Catálogo de regímenes para mapear texto → código SAT
_REGIME_MAP = [
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

_RFC_RE = re.compile(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')

# truststore: una sola vez por proceso; hace que SSL use el almacén del SO (p. ej. Windows),
# alineado con el navegador cuando certifi/OpenSSL del servidor fallan.
_SSL_TRUSTSTORE_INITIALIZED = False
_SSL_TRUSTSTORE_ACTIVE = False


def _sat_init_truststore() -> bool:
    """Activa truststore si está instalado. Devuelve True si las conexiones SSL usan el SO."""
    global _SSL_TRUSTSTORE_INITIALIZED, _SSL_TRUSTSTORE_ACTIVE
    if _SSL_TRUSTSTORE_INITIALIZED:
        return _SSL_TRUSTSTORE_ACTIVE
    _SSL_TRUSTSTORE_INITIALIZED = True
    try:
        import truststore
        truststore.inject_into_ssl()
        _SSL_TRUSTSTORE_ACTIVE = True
        _logger.info(
            'SAT HTTPS: truststore activo (certificados raíz del sistema operativo).'
        )
    except ImportError:
        _SSL_TRUSTSTORE_ACTIVE = False
        _logger.debug(
            'SAT HTTPS: paquete truststore no instalado; se usará certifi u OpenSSL por defecto.'
        )
    except Exception as exc:
        _SSL_TRUSTSTORE_ACTIVE = False
        _logger.warning('SAT HTTPS: truststore no se pudo activar: %s', exc)
    return _SSL_TRUSTSTORE_ACTIVE


def _sat_apply_siat_ssl_compat(ctx: ssl.SSLContext) -> None:
    """
    El portal siat.sat.gob.mx puede ofrecer parámetros DH débiles.
    OpenSSL 3 (Python 3.10+) los rechaza con SECLEVEL=2; los navegadores suelen
    aceptarlos. SECLEVEL=1 alinea el comportamiento sin desactivar verificación.
    """
    for cipher_profile in ('DEFAULT@SECLEVEL=1', 'DEFAULT', 'ALL:@SECLEVEL=1'):
        try:
            ctx.set_ciphers(cipher_profile)
            return
        except ssl.SSLError:
            continue
    _logger.debug(
        'SAT HTTPS: no se pudo aplicar perfil SECLEVEL=1; se usa el contexto por defecto.'
    )


def _sat_build_ssl_context(verify_source) -> ssl.SSLContext:
    """Contexto SSL para requests: verifica certificado y tolera DH del SAT."""
    if verify_source is False:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _sat_apply_siat_ssl_compat(ctx)
        return ctx
    if isinstance(verify_source, str):
        ctx = ssl.create_default_context(cafile=verify_source)
        _sat_apply_siat_ssl_compat(ctx)
        return ctx
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    _sat_apply_siat_ssl_compat(ctx)
    return ctx


class _SATSSLContextAdapter:
    """Adaptador HTTPS compatible con urllib3/requests que no aceptan SSLContext en verify=."""

    def __init__(self, ssl_context: ssl.SSLContext):
        self._ssl_context = ssl_context

    def __call__(self):
        from requests.adapters import HTTPAdapter

        ssl_context = self._ssl_context

        class Adapter(HTTPAdapter):
            def cert_verify(self, conn, url, verify, cert):
                # El SSLContext ya define verificación; requests no debe sobrescribirlo.
                pass

            def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
                pool_kwargs['ssl_context'] = ssl_context
                return super().init_poolmanager(
                    connections, maxsize, block=block, **pool_kwargs
                )

            def proxy_manager_for(self, proxy, **proxy_kwargs):
                proxy_kwargs['ssl_context'] = ssl_context
                return super().proxy_manager_for(proxy, **proxy_kwargs)

        return Adapter()


def _best_regime_code(text: str) -> str | None:
    text_l = text.lower()
    best_code, best_score = None, 0
    for code, keywords in _REGIME_MAP:
        words = [w for w in keywords.lower().split() if len(w) > 3]
        score = sum(1 for w in words if w in text_l)
        if score > best_score:
            best_score = score
            best_code = code
    return best_code


class CsPartnerTaxCertificateSatService(models.AbstractModel):
    """
    Consulta el portal del SAT a partir de la URL contenida en el QR de
    la Constancia de Situación Fiscal y extrae los datos fiscales del
    contribuyente.

    Seguridad:
    - Solo se permiten conexiones HTTPS a siat.sat.gob.mx.
    - No se envían datos del usuario al SAT (GET sin cuerpo).
    - Timeout de 20 s para evitar bloqueos del servidor.
    """
    _name = 'cs.partner.tax.certificate.sat.service'
    _description = 'Consulta de datos fiscales al portal del SAT'

    # ── Punto de entrada público ──────────────────────────────────

    def fetch_fiscal_data(self, url: str) -> dict:
        """
        Valida la URL, realiza la petición y devuelve un dict con:
            rfc, name, zip, fiscal_regime_text, fiscal_regime_code,
            padron_status, start_date, last_update
        En caso de error devuelve {'error': mensaje}.
        """
        self._validate_sat_url(url)
        html = self._fetch_html(url)
        return self._parse_html(html)

    # ── Seguridad ─────────────────────────────────────────────────

    def _validate_sat_url(self, url: str):
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            raise UserError(_('La URL almacenada no tiene un formato válido.'))
        host = parsed.hostname or ''
        if parsed.scheme != 'https':
            raise UserError(_('Solo se permiten URLs HTTPS del portal del SAT.'))
        if host.lower() not in _SAT_ALLOWED_HOSTS:
            raise UserError(
                _('La URL no corresponde al portal oficial del SAT '
                  '(siat.sat.gob.mx). Dominio detectado: %s') % host
            )

    # ── Petición HTTP ─────────────────────────────────────────────

    def _sat_requests_verify_param(self):
        """
        Contexto SSL para requests al consultar siat.sat.gob.mx.

        Orden:
        1) Parámetro ``cs_partner_tax_certificate.sat_ca_bundle``: ruta a un PEM de CAs.
        2) Parámetro ``cs_partner_tax_certificate.sat_ssl_verify`` = false: sin verificar
           (solo entornos con inspección SSL corporativa; riesgo MITM).
        3) truststore (si está instalado): CAs del sistema operativo.
        4) certifi: bundle Mozilla empaquetado en Python.

        Devuelve un ``ssl.SSLContext`` con SECLEVEL=1 para compatibilidad con el SAT.
        """
        icp = self.env['ir.config_parameter'].sudo()
        ca_bundle = (icp.get_param('cs_partner_tax_certificate.sat_ca_bundle') or '').strip()
        if ca_bundle:
            if not os.path.isfile(ca_bundle):
                raise UserError(
                    _('El archivo de certificados CA para el SAT no existe o no es legible: %s')
                    % ca_bundle
                )
            return _sat_build_ssl_context(ca_bundle), 'ca_bundle_file'
        verify_on = icp.get_param('cs_partner_tax_certificate.sat_ssl_verify', 'true')
        if str(verify_on).lower() in ('0', 'false', 'no'):
            _logger.warning(
                'SAT HTTPS: verificación SSL desactivada por parámetro '
                'cs_partner_tax_certificate.sat_ssl_verify (riesgo de seguridad).'
            )
            return _sat_build_ssl_context(False), 'verify_disabled'
        _sat_init_truststore()
        mode = 'truststore_os' if _SSL_TRUSTSTORE_ACTIVE else 'certifi_or_default'
        return _sat_build_ssl_context(True), mode

    def _fetch_html(self, url: str) -> str:
        try:
            import requests
        except ImportError:
            raise UserError(msg_missing_requests())
        verify, verify_mode = self._sat_requests_verify_param()
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        }
        try:
            session = requests.Session()
            session.mount('https://', _SATSSLContextAdapter(verify)())
            resp = session.get(
                url, headers=headers, timeout=_REQUEST_TIMEOUT, verify=True
            )
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            _logger.debug('SAT response status %s, length %d', resp.status_code, len(resp.text))
            return resp.text
        except requests.exceptions.Timeout:
            raise UserError(
                '%s\n\n%s'
                % (
                    msg_sat_unavailable(),
                    _('Tiempo de espera agotado (%d segundos).') % _REQUEST_TIMEOUT,
                )
            )
        except requests.exceptions.SSLError as exc:
            err_text = str(exc).lower()
            _logger.warning(
                'SAT SSLError (modo=%s): %s',
                verify_mode,
                exc,
                exc_info=True,
            )
            if 'dh_key_too_small' in err_text or 'dh key too small' in err_text:
                raise UserError(
                    _('No se pudo establecer la conexión segura con el portal del SAT '
                      '(parámetros criptográficos obsoletos en siat.sat.gob.mx). '
                      'Actualice el módulo cs_partner_tax_certificate a la última versión '
                      'y reinicie Odoo. Si el problema continúa, contacte al administrador.')
                )
            raise UserError(
                _('Error SSL al conectar con el SAT. Verifique que requests, certifi y '
                  'truststore estén instalados en el Python de Odoo y reinicie el servicio. '
                  'Detalle técnico en el registro del servidor.')
            )
        except requests.exceptions.ConnectionError:
            raise UserError(
                '%s\n\n%s'
                % (
                    msg_sat_unavailable(),
                    _('Verifique la conexión a internet del servidor de Odoo.'),
                )
            )
        except requests.exceptions.HTTPError as exc:
            raise UserError(_('El SAT respondió con error HTTP: %s') % str(exc))

    # ── Parseo HTML ───────────────────────────────────────────────

    def _parse_html(self, html: str) -> dict:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise UserError(msg_missing_bs4())
        soup = BeautifulSoup(html, 'html.parser')
        result = {}

        # Domicilio: motor exclusivo HTML SAT (no regex de PDF ni texto de toda la página)
        merge_sat_address_into(result, parse_address_from_html(soup))

        # Identificación, fechas, padrón (tablas / dt-dd / label)
        for row in soup.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            cell_texts = [c.get_text(separator=' ', strip=True) for c in cells]
            if len(cell_texts) >= 4 and len(cell_texts) % 2 == 0:
                for idx in range(0, len(cell_texts), 2):
                    self._map_sat_identity(result, cell_texts[idx], cell_texts[idx + 1])
            elif len(cell_texts) >= 2:
                self._map_sat_identity(result, cell_texts[0], cell_texts[1])

        for dt in soup.find_all('dt'):
            dd = dt.find_next_sibling('dd')
            if dd:
                self._map_sat_identity(
                    result,
                    dt.get_text(strip=True),
                    dd.get_text(strip=True),
                )

        for label_tag in soup.find_all('label'):
            sib = label_tag.find_next_sibling(['span', 'div', 'td', 'p'])
            if sib:
                self._map_sat_identity(
                    result,
                    label_tag.get_text(strip=True),
                    sib.get_text(strip=True),
                )

        regimenes = parse_regimes_from_html(soup)
        if regimenes:
            result['fiscal_regime_text'] = ' | '.join(dict.fromkeys(regimenes))
            result['fiscal_regime_code'] = _best_regime_code(regimenes[0])

        self._compose_pf_full_name(result)

        if not result:
            _logger.warning(
                'SAT: no se pudieron extraer datos de la respuesta HTML. '
                'El SAT pudo haber cambiado el formato de la página.'
            )
            result['warning'] = msg_sat_format_changed()
        return result

    def _compose_pf_full_name(self, result: dict) -> None:
        """Une razón social o Nombre(s) + apellidos (persona física)."""
        moral = result.pop('_moral_name', None)
        if moral:
            result['name'] = moral
            result.pop('_pf_nombre', None)
            result.pop('_pf_apellido_paterno', None)
            result.pop('_pf_apellido_materno', None)
            return

        nombre = result.pop('_pf_nombre', None)
        ap_pat = result.pop('_pf_apellido_paterno', None)
        ap_mat = result.pop('_pf_apellido_materno', None)
        if ap_pat or ap_mat:
            parts = [p for p in (nombre, ap_pat, ap_mat) if p]
            if parts:
                result['name'] = ' '.join(parts)
                return
        if nombre:
            result['name'] = nombre

    @staticmethod
    def _is_moral_name_label(label_l: str) -> bool:
        if 'nombre de' in label_l:
            return False
        return (
            'denominación' in label_l
            or 'denominacion' in label_l
            or 'razón social' in label_l
            or 'razon social' in label_l
        )

    @staticmethod
    def _is_pf_nombre_label(label_l: str) -> bool:
        if 'apellido' in label_l or 'nombre de' in label_l:
            return False
        if label_l in ('nombre', 'nombre(s)', 'nombre (s)'):
            return True
        return label_l.startswith('nombre (s)') or label_l.startswith('nombre(s)')

    # ── Identificación (sin domicilio ni régimen; eso va en sat_address_parser) ──

    def _map_sat_identity(self, result: dict, label: str, value: str):
        if not label or not value:
            return
        label_l = _normalize_label(label)
        value = re.sub(r'\s+', ' ', value).strip()
        if not value or value in ('-', 'N/A', 'n/a'):
            return

        if _resolve_address_label(label_l):
            return
        if any(kw in label_l for kw in ('regimen', 'vialidad', 'colonia', 'codigo postal', 'municipio')):
            return

        if re.fullmatch(r'rfc', label_l) or label_l.startswith('rfc'):
            rfc = re.sub(r'\s+', '', value).upper()
            if _RFC_RE.match(rfc):
                result.setdefault('rfc', rfc)

        elif 'apellido paterno' in label_l or label_l.startswith('primer apellido'):
            result.setdefault('_pf_apellido_paterno', value)

        elif 'apellido materno' in label_l or label_l.startswith('segundo apellido'):
            result.setdefault('_pf_apellido_materno', value)

        elif self._is_moral_name_label(label_l):
            result.setdefault('_moral_name', value)

        elif self._is_pf_nombre_label(label_l):
            result.setdefault('_pf_nombre', value)

        elif any(kw in label_l for kw in (
            'estatus', 'estado en el padrón', 'estado en el padron',
        )):
            result.setdefault('padron_status', value.upper())

        elif any(kw in label_l for kw in (
            'fecha inicio', 'inicio de operaciones',
        )):
            result.setdefault('start_date', value)

        elif any(kw in label_l for kw in (
            'última actualización', 'ultima actualizacion',
            'fecha de actualización', 'fecha de actualizacion',
        )):
            result.setdefault('last_update', value)
