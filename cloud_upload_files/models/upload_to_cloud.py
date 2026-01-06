import base64
import logging
import json  # <--- Agregamos esto
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    from google.cloud import storage
except ImportError:
    storage = None

_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def action_upload_to_gcs(self):
        if not storage:
            raise UserError(_("Librería google-cloud-storage no instalada."))

        bucket_name = self.env['ir.config_parameter'].sudo().get_param('cloud_storage_google_bucket_name')
        json_data = self.env['ir.config_parameter'].sudo().get_param('cloud_storage_google_account_info')
        
        if not bucket_name or not json_data:
            raise UserError(_("Faltan parámetros de configuración GCS."))

        try:
            # --- NUEVA LÓGICA PARA DETECTAR SI ES JSON O RUTA ---
            if json_data.strip().startswith('{'):
                # Es el contenido del JSON (texto)
                info = json.loads(json_data)
                client = storage.Client.from_service_account_info(info)
            else:
                # Es una ruta de archivo
                client = storage.Client.from_service_account_json(json_data)
            
            bucket = client.bucket(bucket_name)
        except Exception as e:
            raise UserError(_("Error con las credenciales de Google: %s") % str(e))

        # ... (el resto del código de subida se mantiene igual) ...
        ALLOWED_EXTENSIONS = ('.pdf', '.jpeg', '.jpg', '.mp4', '.zip')
        count = 0
        for attachment in self:
            # Solo procesar archivos binarios (evitar procesar URLs ya existentes)
            if attachment.type == 'url' or not attachment.datas:
                continue
                
            if attachment.name and attachment.name.lower().endswith(ALLOWED_EXTENSIONS) and attachment.datas:
                #raise UserError("Si entra al if")
                try:
                    file_content = base64.b64decode(attachment.datas)
                    blob_name = f"{self.env.cr.dbname}/{attachment.id}_{attachment.name}"
                    blob = bucket.blob(blob_name)
                    blob.upload_from_string(file_content, content_type=attachment.mimetype)
                    # 4. Obtener la URL pública
                    # Nota: El bucket debe tener permisos de lectura pública o estar configurado para ello.
                    public_url = blob.public_url
                    attachment.write({
                        'type': 'cloud_storage',
                        'url': public_url,
                        'datas': False,      # Borramos el archivo físico de Odoo para liberar espacio
                        'db_datas': False,   # Limpieza en base de datos
                        #'mimetype': content_type,
                        'description': f"En GCS: {blob_name}"
                    })
                    count += 1
                except Exception as e:
                    _logger.error("Error en %s: %s", attachment.id, str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _('Se subieron %s archivos y se liberó espacio.') % count,
                'type': 'success',
            }
        }