import logging

from odoo.http import Stream
from odoo.http import request
_logger = logging.getLogger(__name__)

class StreamInherit(Stream):

    @classmethod
    def load_gcs_attachment(cls, attachment):
        attachment.ensure_one()
        self = cls(
            mimetype=attachment.mimetype,
            download_name=attachment.name,
            conditional=True,
            etag=attachment.checksum,
        )

        self.type = 'data'
        self.data = request.env['ir.attachment']._file_read(attachment.store_fname)
        self.last_modified = attachment['__last_update']
        self.size = len(self.data)
        return self

Stream.load_gcs_attachment = StreamInherit.load_gcs_attachment