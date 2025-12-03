# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
from odoo.http import Stream
from odoo import models
from odoo.exceptions import MissingError, UserError

class IrBinary(models.AbstractModel):
    _inherit = 'ir.binary'

    def _record_to_stream(self, record, field_name):
        try:
            if record._name == 'ir.attachment' and field_name in ('raw', 'datas', 'db_datas') and record.store_fname:
                return Stream.load_gcs_attachment(record)
            record.check_field_access_rights('read', [field_name])
            field_def = record._fields[field_name]

            # fields.Binary(attachment=False) or compute/related
            if not field_def.attachment or field_def.compute or field_def.related:
                return Stream.from_binary_field(record, field_name)

            # fields.Binary(attachment=True)
            field_attachment = self.env['ir.attachment'].sudo().search(
                domain=[('res_model', '=', record._name),
                        ('res_id', '=', record.id),
                        ('res_field', '=', field_name)],
                limit=1)
            if not field_attachment:
                raise MissingError("The related attachment does not exist.")
            return Stream.load_gcs_attachment(field_attachment)
        except:
            return super()._record_to_stream(record, field_name)