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
from odoo import api, fields, models, exceptions
import base64
import os
import logging
_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.depends("file_selector")
    def _check_and_save(self):
        if self.file_selector:
            try:
                name='google_cred.json'
                attachment_rec = self.env['ir.attachment'].sudo().search([('name', '=', name), ('res_model', '=', 'res.config.settings')], limit=1)
                if attachment_rec:
                    self.env['ir.attachment'].sudo().write({
                        'datas': self.file_selector,
                        'mimetype': 'application/json', 
                        })
                else:
                    attachment_rec = {
                                    'name': name,
                                    'datas': self.file_selector,
                                    'type': 'binary',
                                    'mimetype': 'application/json', 
                                    'res_model': 'res.config.settings',
                                }
                    attachment_rec = self.env['ir.attachment'].sudo().create(attachment_rec)

                self.google_cloud_storage_key_path = self.env['ir.attachment']._full_path(attachment_rec.store_fname)

            except Exception as e:
                _logger.info(" Error in credential file creation ...%r",e)
                raise exceptions.ValidationError('Not valid message')
        else:
            self.google_cloud_storage_key_path=False


    cloud_bucket_name = fields.Char(
        string='Bucket Name', config_parameter = 'google_cloud_storage.cloud_bucket_name', help="This allows users to store data in Bucket.")
    google_cloud_storage_key_path = fields.Char(
        string='Credential File Path', config_parameter = 'google_cloud_storage.google_cloud_storage_key_path', help="Google cloud storage credential key json file.", compute= "_check_and_save",default="")
    activate_gc_storage = fields.Boolean(string='Activate Storage', config_parameter = 'google_cloud_storage.activate_gc_storage')



    file_selector = fields.Binary(help= "select your google cloud storage key file")
