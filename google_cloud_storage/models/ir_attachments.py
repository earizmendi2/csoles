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
import base64
from odoo import api, models, fields, _

from google.cloud import storage

import logging
_logger = logging.getLogger(__name__)

cloud_bucket_instance = False

class GoogleCloudAttachment(models.Model):

    _inherit = "ir.attachment"


    # For passing mimetype to _file_write
    def _get_datas_related_values(self, data, mimetype):

        self = self.with_context(content_type = mimetype)
        return super()._get_datas_related_values(data,mimetype)


    # for creating a instance of Google Cloud Storage Bucket
    def get_bucket(self):
        global cloud_bucket_instance
        try:
            params = self.env['ir.config_parameter'].sudo()
            json_file = params.get_param('google_cloud_storage.google_cloud_storage_key_path')
            bucket = params.get_param('google_cloud_storage.cloud_bucket_name')
            activate_google_cloud = params.get_param('google_cloud_storage.activate_gc_storage')
            if activate_google_cloud:
                if json_file:
                    client = storage.Client.from_service_account_json(json_file)
                if bucket:
                    cloud_bucket = client.get_bucket(bucket)
                    cloud_bucket_instance = cloud_bucket
        except Exception as e:
            _logger.info("Error: problem in googel connection ... %r",e)
        return True


    # for creating a path for the _file_write
    def _set_cloud_blob_name(self, checksum):

        dbname = self._cr.dbname
        fname = checksum[:2] + '/' + checksum
        return fname, '/'.join([dbname, fname])


    # for creating a path for the _file_read
    @api.model
    def _get_cloud_blob_name(self,fname):

        dbname = self._cr.dbname
        blob_name = fname
        return '/'.join([dbname, blob_name])


    # for reading from the cloud
    @api.model
    def _file_read(self, fname):

        if not cloud_bucket_instance:
            self.get_bucket()
        if cloud_bucket_instance:
            try:
                blob_name = self._get_cloud_blob_name(fname)
                blob = cloud_bucket_instance.blob(blob_name)
                read = blob.download_as_string()
                return read
            except Exception as e:
                _logger.info("ERROR 404: File not found on Google Cloud Bucket...%r",e)
        return super(GoogleCloudAttachment, self)._file_read(fname)


    # for writing into the cloud
    @api.model
    def _file_write(self, value, checksum):

        if not cloud_bucket_instance:
            self.get_bucket()
        if cloud_bucket_instance:
            fname, blob_name = self._set_cloud_blob_name(checksum)
            blob = cloud_bucket_instance.blob(blob_name)
            content_type = self._context.get("content_type", "text/plain")
            blob.upload_from_string(value,content_type = content_type)
        else:
            fname = super(GoogleCloudAttachment, self)._file_write(value, checksum)
        return fname


    # for deleting from the cloud
    def _mark_for_gc(self, fname):
        if not cloud_bucket_instance:
            self.get_bucket()
        if cloud_bucket_instance:
            try:
                blob_name = self._get_cloud_blob_name('checklist/%s' % fname)
                blob = cloud_bucket_instance.blob(blob_name)
                value = base64.b64decode('')
                blob.upload_from_string(value)
                _logger.debug('Google Cloud Storage: _mark_for_gc key:%s marked for GC', blob_name)
            except Exception as e:
                _logger.error('Google Cloud Storage: File mark as GC, Storage %r,Exception %r', (storage,e))
        else:
            super(GoogleCloudAttachment, self)._mark_for_gc(fname)


    @api.autovacuum
    def _gc_file_store(self):
        """ Perform the garbage collection of the filestore. """
        if not cloud_bucket_instance:
            self.get_bucket()
        if cloud_bucket_instance:
            cr = self._cr
            cr.commit()
            cr.execute("LOCK ir_attachment IN SHARE MODE")
            checklist = {}
            whitelist = set()
            removed = 0
            try:
                if not cloud_bucket_instance:
                    self.get_bucket()
                for gc_blob_name in cloud_bucket_instance.list_blobs(Prefix=self._get_cloud_blob_name('checklist')):
                    key = self._get_cloud_blob_name(gc_blob_name[1 + len(self._get_cloud_blob_name('checklist/')):])
                    checklist[key] = gc_blob_name

                for names in cr.split_for_in_conditions(checklist):
                    cr.execute("SELECT store_fname FROM ir_attachment WHERE store_fname IN %s", [names])
                    whitelist.update(row[0] for row in cr.fetchall())

                for key, value in checklist.iteritems():
                    if key not in whitelist:
                        #remove checklist blob
                        cloud_bucket_instance.delete_blob(key)
                        #remove original blob
                        cloud_bucket_instance.delete_blob(value)
                        removed += 1
                        _logger.info('Google Cloud Storage: _file_gc_ deleted key:%s successfully', key)
            except Exception as e:
                _logger.error('Google Cloud Storage: _file_gc_ method delete : EXCEPTION %r'% (e))
            cr.commit()
            _logger.debug("Google Cloud Storage: filestore gc %d checked, %d removed", len(checklist), removed)
        else:
            super(GoogleCloudAttachment, self)._gc_file_store()
