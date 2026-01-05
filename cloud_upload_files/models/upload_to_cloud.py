# models/attachment_ext.py
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

# Aquí SÍ puedes importar librerías externas
try:
    from google.cloud import storage
except ImportError:
    storage = None

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def action_upload_to_gcs(self):
        if not storage:
            raise UserError("La librería google-cloud-storage no está instalada.")

        attachment = env['ir.attachment'].search([('name', '=', 'google_cred.json')], limit=1)
        if not attachment:
            raise UserError("El archivo adjunto google_storage_key.json no existe") 

        json_data = json.loads(base64.b64decode(attachment.datas))
        
        BUCKET_NAME = "odoo-gcs-service-staging"
        client = storage.Client.from_service_account_json(json_file_path)
        #client = storage.Client.from_service_account_info(json_data)
        bucket = client.get_bucket(BUCKET_NAME)

        for attachment in self:
            if attachment.type == 'url':
                continue
            
            file_content = base64.b64decode(attachment.datas)
            file_name = f"odoo_files/{attachment.id}_{attachment.name}"
            blob = bucket.blob(file_name)
            
            blob.upload_from_string(file_content, content_type=attachment.mimetype)
            
            attachment.write({
                'type': 'url',
                'url': blob.public_url,
                'datas': False,
            })
            