import logging
import unicodedata

from odoo import models

_logger = logging.getLogger(__name__)


class CsPartnerTaxCertificateParser(models.AbstractModel):
    _inherit = 'cs.partner.tax.certificate.parser'

    def _extract_text(self, pdf_bytes):
        """Usa PyMuPDF (fitz) en vez de PyPDF2 para leer el texto del PDF.

        PyMuPDF reconstruye los espacios entre palabras a partir de la
        posición real de cada carácter, mucho más confiable que PyPDF2 para
        la fuente que usa la Constancia de Situación Fiscal del SAT (con
        PyPDF2 a veces sale pegada sin espacios, o separada letra por letra).

        Si PyMuPDF no está disponible o falla por cualquier motivo, se cae
        al comportamiento original del módulo (PyPDF2) vía super(), sin
        romper nada.
        """
        text = self._extract_text_with_fitz(pdf_bytes)
        if text is not None:
            # NFKC: convierte 'o' + acento combinante → 'ó' (igual que el original).
            return unicodedata.normalize('NFKC', text), None
        return super()._extract_text(pdf_bytes)

    @staticmethod
    def _extract_text_with_fitz(pdf_bytes):
        try:
            import fitz  # pymupdf
        except ImportError:
            _logger.info(
                'CIFParser (parche local): pymupdf no disponible, '
                'usando PyPDF2 como en el módulo original.'
            )
            return None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype='pdf')
            try:
                pages = [page.get_text('text') or '' for page in doc]
            finally:
                doc.close()
            text = '\n'.join(pages)
            return text if text.strip() else None
        except Exception:  # noqa: BLE001 - cualquier falla cae a PyPDF2, no debe tronar el import
            _logger.exception(
                'CIFParser (parche local): fitz falló extrayendo texto, '
                'usando PyPDF2 como respaldo.'
            )
            return None
