# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
import base64
import io
from PyPDF2 import PdfFileReader, PdfFileWriter
from PIL import Image, UnidentifiedImageError
import pikepdf
import subprocess
import tempfile
import os


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _is_pdf(self, file_bytes):
        return file_bytes.startswith(b'%PDF')

    def _is_image(self, file_bytes):
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.load()
            return True
        except Exception:
            return False

    def compress_pdf_ghostscript(self, file_bytes):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as input_tmp:
            input_tmp.write(file_bytes)
            input_tmp.flush()
            input_name = input_tmp.name

        output_name = input_name.replace(".pdf", "_compressed.pdf")

        gs_command = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/ebook',
            '-dNOPAUSE',
            '-dQUIET',
            '-dBATCH',
            f'-sOutputFile={output_name}',
            input_name
        ]

        try:
            subprocess.run(gs_command, check=True)

            with open(output_name, 'rb') as f_out:
                compressed_data = f_out.read()
        finally:
            # Clean up temp files
            os.remove(input_name)
            if os.path.exists(output_name):
                os.remove(output_name)

        return compressed_data

    def _compress_pdf(self, file_bytes):
        try:
            return self.compress_pdf_ghostscript(file_bytes)
        except Exception as e:
            return file_bytes

    def _compress_image(self, file_bytes):
        try:
            image = Image.open(io.BytesIO(file_bytes))
            output = io.BytesIO()
            if image.format in ['JPEG', 'JPG']:
                image.save(output, format='JPEG', quality=30, optimize=True)
            elif image.format == 'PNG':
                image.save(output, format='PNG', optimize=True)
            else:
                image = image.convert('RGB')
                image.save(output, format='JPEG', quality=30, optimize=True)
            return output.getvalue()
        except Exception as e:
            return file_bytes

    def compress_large_files(self):

        allowed_mimetypes = [
            'application/pdf',
            'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/jpg'
        ]

        attachments = self.search([
            ('type', '=', 'binary'),
            ('mimetype', 'in', allowed_mimetypes),
        ])

        for attachment in attachments:
            try:
                if not attachment.datas:
                    continue  # Skip if there's no data

                decoded = base64.b64decode(attachment.datas)
                original_size = len(decoded)
                if original_size < 10 * 1024:
                    continue  # Skip small files

                if self._is_pdf(decoded):
                    compressed = self._compress_pdf(decoded)
                elif self._is_image(decoded):
                    compressed = self._compress_image(decoded)
                else:
                    continue

                compressed_size = len(compressed) if compressed else original_size
                if compressed and compressed_size < original_size:
                    attachment.datas = base64.b64encode(compressed)
            except Exception:
                pass


