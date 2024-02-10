# -*- coding: utf-8 -*-

import base64
import io

import subprocess
import tempfile
import time
import zipfile
# import datetime
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from functools import partial
from lxml import etree, objectify
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from .sat_api_import import SAT
from .special_dict import CaselessDictionary
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from time import sleep
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from .portal_sat import PortalSAT

import logging
_logger = logging.getLogger(__name__)

TYPE_CFDI22_TO_CFDI33 = {
    'ingreso': 'I',
    'egreso': 'E',
    'traslado': 'T',
    'nomina': 'N',
    'pago': 'P',
}

ERROR_TYPE = [(0, 'Token invalido.'), (1, 'Aceptada'), (2, 'En proceso'), (3, 'Terminada'), (4, 'Error'),
              (5, 'Rechazada'), (6, 'Vencida')]
TRY_COUNT = 3
KEY_TO_PEM_CMD = 'openssl pkcs8 -in %s -inform der -outform pem -out %s -passin file:%s'





class ResCompany(models.Model):
    _inherit = 'res.company'

    def save_downloaded_content(self, esignature, sat_obj, solicitud, customer_documents):
        content = []
        for _ in range(10):
            token = sat_obj.soap_generate_token(sat_obj.certificate, sat_obj.private_key)
            verificacion = sat_obj.soap_verify_package(esignature.holder_vat, solicitud['id_solicitud'], token)
            #_logger.info(f'\n >>> SOLICITUD: {verificacion}')
            estado_solicitud = int(verificacion['estado_solicitud'])
            # 0, Token invalido.
            # 1, Aceptada
            # 2, En proceso
            # 3, Terminada
            # 4, Error
            # 5, Rechazada
            # 6, Vencida
            if estado_solicitud <= 2:
                # Si el estado de solicitud esta Aceptado o en proceso el programa espera
                # 60 segundos y vuelve a tratar de verificar
                time.sleep(30)
                continue
            elif estado_solicitud >= 4:
                message = f"{ERROR_TYPE[estado_solicitud]} - {verificacion['mensaje']}"
                #_logger.info(f"\n >>> {message}")
                self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
                                             {'title': "Error", 'message': message, 'sticky': False, 'warning': True})
                break
            else:
                # Si el estatus es 3 se trata de descargar los paquetes
                for paquete in verificacion['paquetes']:
                    descarga = sat_obj.soap_download_package(esignature.holder_vat, paquete, token)
                    content.append(descarga['paquete_b64'])
                break
        if not content:
            return True
        attachment_obj = self.env['ir.attachment']
        invoice_obj = self.env['account.move']
        payment_obj = self.env['account.payment']
        NSMAP = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
            'pago10': 'http://www.sat.gob.mx/Pagos',
        }

        # Supplier
        attach_obj = self.env['ir.attachment'].sudo()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(content[0]))) as z:
            for attachment_name in z.namelist():
                with z.open(attachment_name) as att_xml:
                    xml_content = att_xml.read()
                    cfdi_etree = self._check_objectify_xml(base64.b64encode(xml_content))
                    tfd_node = self._get_et_cfdi_node(cfdi_etree)
                    uuid = tfd_node.get('UUID').upper().strip() if tfd_node.get('UUID') else 'No firmado'
                    attachments = attach_obj.search([
                        ('cfdi_uuid', '=', uuid),
                        ('company_id', '=', self.id)])
                    if attachments:
                        continue
                    try:
                        values = dict(etree.fromstring(xml_content).items())
                    except:
                        continue
                    if b'xmlns:schemaLocation' in xml_content:
                        xml_content = xml_content.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
                    try:
                        tree = etree.fromstring(xml_content)
                    except Exception as e:
                        self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
                                             {'title': "Error", 'message': "No pudo leer un XML descargado", 'sticky': False, 'warning': True})
                        _logger.error('error etree.fromstring: ' + str(e))
                        continue
                    try:
                        ns = tree.nsmap
                        ns.update({'re': 'http://exslt.org/regular-expressions'})
                    except Exception:
                        ns = {'re': 'http://exslt.org/regular-expressions'}

                    xml_content = base64.b64encode(xml_content)

                    ns_url = ns.get('cfdi')
                    root_tag = 'Comprobante'
                    if ns_url:
                        root_tag = '{' + ns_url + '}Comprobante'
                    # Validation to only admit CFDI
                    if tree.tag != root_tag:
                        # Invalid invoice file.
                        continue

                    # receptor_elements = tree.xpath('//cfdi:Emisor', namespaces=tree.nsmap)
                    if customer_documents:
                        try:
                            emisor_elements = tree.xpath("//*[re:test(local-name(), 'Receptor','i')]", namespaces=ns)
                        except Exception:
                            _logger.info("No encontró al receptor")
                        r_rfc, r_name, r_folio = '', '', ''
                        if emisor_elements:
                            attrib_dict = CaselessDictionary(dict(emisor_elements[0].attrib))
                            r_rfc = attrib_dict.get('rfc')  # emisor_elements[0].get(attrib_dict.get('rfc'))
                            r_name = attrib_dict.get('nombre')  # emisor_elements[0].get(attrib_dict.get('nombre'))
                    else:
                        try:
                            receptor_elements = tree.xpath("//*[re:test(local-name(), 'Emisor','i')]", namespaces=ns)
                        except Exception:
                            receptor_elements = False
                            _logger.info("No encontró al emisor")
                        r_rfc, r_name, r_folio = '', '', ''
                        if receptor_elements:
                            attrib_dict = CaselessDictionary(dict(receptor_elements[0].attrib))
                            r_rfc = attrib_dict.get('rfc')  # receptor_elements[0].get(attrib_dict.get('rfc'))
                            r_name = attrib_dict.get('nombre')  # receptor_elements[0].get(attrib_dict.get('nombre'))
                    r_folio = str(tree.get("Serie")) + str(tree.get("Folio"))  # receptor_elements[0].get(attrib_dict.get('nombre'))

                    cfdi_version = tree.get("Version", '4.0')
                    if cfdi_version == '4.0':
                        NSMAP.update(
                            {'cfdi': 'http://www.sat.gob.mx/cfd/4', 'pago20': 'http://www.sat.gob.mx/Pagos20', })
                    else:
                        NSMAP.update(
                            {'cfdi': 'http://www.sat.gob.mx/cfd/3', 'pago10': 'http://www.sat.gob.mx/Pagos', })

                    cfdi_type = tree.get("TipoDeComprobante", 'I')
                    if cfdi_type not in ['I', 'E', 'P', 'N', 'T']:
                        cfdi_type = 'I'
                    if not customer_documents:
                        cfdi_type = 'S' + cfdi_type

                    monto_total = 0
                    if cfdi_type in ['SP', 'P']:
                        complemento = tree.find('cfdi:Complemento', NSMAP)
                        if cfdi_version == '4.0':
                           pagos = complemento.find('pago20:Pagos', NSMAP)
                           pago = pagos.find('pago20:Totales', NSMAP)
                           monto_total = pago.attrib['MontoTotalPagos']
                        else:
                           pagos = complemento.find('pago10:Pagos', NSMAP)
                           try:
                              pago = pagos.find('pago10:Pago',NSMAP)
                              monto_total = pago.attrib['Monto']
                           except Exception as e:
                              for payment in pagos.find('pago10:Pago',NSMAP):
                                  monto_total += float(payment.attrib['Monto'])
                    else:
                        monto_total = tree.get('Total', 0.0)

                    filename = uuid + '.xml'  # values.get('receptor','')[:10]+'_'+values.get('rfc_receptor')
                    vals = dict(
                        name=filename,
                        store_fname=filename,
                        type='binary',
                        datas=xml_content,
                        cfdi_uuid=uuid,
                        company_id=self.id,
                        cfdi_type=cfdi_type,
                        rfc_tercero=r_rfc,
                        nombre_tercero=r_name,
                        serie_folio=r_folio,
                        cfdi_total=monto_total,
                    )
                    vals.update({'date_cfdi': tree.get('Fecha')})  # .strftime(DEFAULT_SERVER_DATE_FORMAT)})
                    if customer_documents:
                        if cfdi_type == 'P':
                            for uu in [uuid, uuid.lower(), uuid.upper()]:
                                payment_exist = payment_obj.search([('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('company_id','=',self.id)], limit=1)
                                if payment_exist:
                                    vals.update({'creado_en_odoo': True, 'payment_ids': [(6, 0, payment_exist.ids)]})
                                    break
                        elif cfdi_type == 'E':
                            for uu in [uuid, uuid.lower(), uuid.upper()]:
                                invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('company_id','=',self.id)], limit=1)
                                if invoice_exist:
                                    vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
                                    break
                        else:
                            for uu in [uuid, uuid.lower(), uuid.upper()]:
                                invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('company_id','=',self.id)], limit=1)
                                if invoice_exist:
                                    vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
                                    break
                    else:
                        if cfdi_type == 'SP':
                            for uu in [uuid, uuid.lower(), uuid.upper()]:
                                payment_exist = payment_obj.search(
                                    [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('payment_type', '=', 'outbound'), ('company_id','=',self.id)], limit=1)
                                if payment_exist:
                                    vals.update({'creado_en_odoo': True, 'payment_ids': [(6, 0, payment_exist.ids)]})
                                    break
                        elif cfdi_type == 'SE':
                            for uu in [uuid, uuid.lower(), uuid.upper()]:
                                invoice_exist = invoice_obj.search(
                                    [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('move_type', '=', 'in_refund'), ('company_id','=',self.id)], limit=1)
                                if invoice_exist:
                                    vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
                                    break
                        else:
                            for uu in [uuid, uuid.lower(), uuid.upper()]:
                                invoice_exist = invoice_obj.search(
                                    [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('move_type', '=', 'in_invoice'), ('company_id','=',self.id)], limit=1)
                                if invoice_exist:
                                    vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
                                    break
                    attachment_obj.create(vals)

    ##### Download by web
    def download_cfdi_invoices_web(self, start_date=False, end_Date=False):
        esignature_ids = self.l10n_mx_esignature_ids
        esignature = esignature_ids.with_user(self.env.user).get_valid_certificate()
        requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'

        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        session.get('https://cfdiau.sat.gob.mx/')

        if not esignature:
            raise UserError("Archivos incorrectos no son una FIEL.")

        if not esignature.content or not esignature.key or not esignature.password:
            raise UserError("Seleccine los archivos FIEL .cer o FIEL .pem.")

        fiel_cert_data = base64.b64decode(esignature.content)
        fiel_pem_data = convert_key_cer_to_pem(base64.decodebytes(esignature.key), esignature.password.encode('UTF-8'))

        opt= {'credenciales':None,'rfc':None, 'uuid': None, 'ano': None, 'mes': None, 'dia': 0, 'intervalo_dias':None, 'fecha_inicial': None, 'fecha_final': None, 'tipo':'t', 'tipo_complemento':'-1', 'rfc_emisor': None, 'rfc_receptor': None, 'sin_descargar':False, 'base_datos': False, 'directorio_fiel' : '', 'archivo_uuids' : '', 'estatus':False}
        today = datetime.utcnow()
        if start_date and end_Date:
            opt['fecha_inicial'] = start_date
            opt['fecha_final'] = end_Date
        elif self.last_cfdi_fetch_date:
            last_import_date = self.last_cfdi_fetch_date #datetime.strptime(self.last_cfdi_fetch_date,DEFAULT_SERVER_DATETIME_FORMAT)
            last_import_date - relativedelta(days=2)

            fecha_inicial = last_import_date - relativedelta(days=2)
            fecha_final = today + relativedelta(days=2)
            opt['fecha_inicial'] = fecha_inicial
            opt['fecha_final'] = fecha_final
        else:
            ano = today.year
            mes = today.month
            opt['ano']=ano
            opt['mes']=mes

        sat = False
        for i in range(TRY_COUNT):
            sat = PortalSAT(opt['rfc'], 'cfdi-descarga', False)
            if sat.login_fiel(fiel_cert_data, fiel_pem_data):
                time.sleep(1)
                break
        invoice_content_receptor, invoice_content_emisor = {}, {}
        if sat and sat.is_connect:
            if self.solo_documentos_de_proveedor:
                invoice_content_receptor, invoice_content_emisor = sat.search(opt, 'supplier')
            else:
                invoice_content_receptor, invoice_content_emisor = sat.search(opt)
            sat.logout()
        elif sat:
            sat.logout()
        attachment_obj = self.env['ir.attachment']
        invoice_obj = self.env['account.move']
        payment_obj = self.env['account.payment']
        NSMAP = {
                 'xsi':'http://www.w3.org/2001/XMLSchema-instance',
                 'cfdi':'http://www.sat.gob.mx/cfd/3', 
                 'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
                 'pago10': 'http://www.sat.gob.mx/Pagos',
                 }

        #Supplier
        if invoice_content_receptor:
            uuids = list(invoice_content_receptor.keys())
            attachments = attachment_obj.sudo().search([('cfdi_uuid','in',uuids), ('company_id', '=', self.id)])
            exist_uuids = attachments.mapped('cfdi_uuid')
            for uuid,data in invoice_content_receptor.items():
                if uuid in exist_uuids:
                    continue
                values = data[0]
                xml_content = data[1]
                #tree = etree.fromstring(xml_content)
                if b'xmlns:schemaLocation' in xml_content:
                    xml_content = xml_content.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
                elif b'Ya no puedes descargar' in xml_content:
                    _logger.info('Ya no puedes descargar más documentos. Por seguridad únicamente se permite descargar un máximo de 2,000 archivos por día.')
                    continue
                try:
                    tree = etree.fromstring(xml_content)
                except Exception as e:
                    self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
                                             {'title': "Error", 'message': "No pudo leer un XML descargado", 'sticky': False, 'warning': True})
                    _logger.error('error recibida schema: ' + str(e))
                    continue
                try:
                    ns = tree.nsmap
                    ns.update({'re': 'http://exslt.org/regular-expressions'})
                except Exception:
                    ns = {'re': 'http://exslt.org/regular-expressions'}

                xml_content = base64.b64encode(xml_content)

                ns_url = ns.get('cfdi')
                root_tag = 'Comprobante'
                if ns_url:
                    root_tag = '{'+ns_url+'}Comprobante'
                #Validation to only admit CFDI
                if tree.tag != root_tag:
                    #Invalid invoice file.
                    continue

                #receptor_elements = tree.xpath('//cfdi:Emisor', namespaces=tree.nsmap)
                try:
                    receptor_elements = tree.xpath("//*[re:test(local-name(), 'Emisor','i')]", namespaces=ns)
                except Exception:
                    receptor_elements=False
                    _logger.info("No encontró al emisor")
                r_rfc, r_name, r_folio = '', '',''
                if receptor_elements:
                    attrib_dict = CaselessDictionary(dict(receptor_elements[0].attrib))
                    r_rfc = attrib_dict.get('rfc') #receptor_elements[0].get(attrib_dict.get('rfc'))
                    r_name = attrib_dict.get('nombre') #receptor_elements[0].get(attrib_dict.get('nombre'))
                r_folio = str(tree.get("Serie")) + str(tree.get("Folio")) #receptor_elements[0].get(attrib_dict.get('nombre'))
                cfdi_version = tree.get("Version",'4.0')
                if cfdi_version=='4.0':
                    NSMAP.update({'cfdi':'http://www.sat.gob.mx/cfd/4', 'pago20': 'http://www.sat.gob.mx/Pagos20',})
                else:
                    NSMAP.update({'cfdi':'http://www.sat.gob.mx/cfd/3', 'pago10': 'http://www.sat.gob.mx/Pagos',})
                    
                    
                cfdi_type = tree.get("TipoDeComprobante",'I')
                if cfdi_type not in ['I','E','P','N','T']:
                    cfdi_type = 'I'
                cfdi_type ='S'+cfdi_type

                monto_total = 0
                if cfdi_type=='SP':
                        complemento = tree.find('cfdi:Complemento', NSMAP)
                        if cfdi_version == '4.0':
                           pagos = complemento.find('pago20:Pagos', NSMAP)
                           pago = pagos.find('pago20:Totales', NSMAP)
                           monto_total = pago.attrib['MontoTotalPagos']
                        else:
                           pagos = complemento.find('pago10:Pagos', NSMAP)
                           try:
                              pago = pagos.find('pago10:Pago',NSMAP)
                              monto_total = pago.attrib['Monto']
                           except Exception as e:
                              for payment in pagos.find('pago10:Pago',NSMAP):
                                  monto_total += float(payment.attrib['Monto'])
                else:
                    monto_total = values.get('total',0.0)

                filename = uuid + '.xml' #values.get('receptor','')[:10]+'_'+values.get('rfc_receptor')
                vals = dict(
                        name=filename,
                        store_fname=filename,
                        type='binary',
                        datas=xml_content,
                        cfdi_uuid=uuid,
                        company_id=self.id,
                        cfdi_type=cfdi_type,
                        rfc_tercero = r_rfc,
                        nombre_tercero = r_name,
                        serie_folio = r_folio,
                        cfdi_total = monto_total,
                    )
                if values.get('date_cfdi'):
                    vals.update({'date_cfdi' : values.get('date_cfdi').strftime(DEFAULT_SERVER_DATE_FORMAT)})
                if cfdi_type=='SP':
                    for uu in [uuid,uuid.lower(),uuid.upper()]:
                        payment_exist = payment_obj.search([('l10n_mx_edi_cfdi_uuid_cusom','=',uu),('payment_type','=','outbound'), ('company_id','=',self.id)],limit=1)
                        if payment_exist:
                            vals.update({'creado_en_odoo' : True,'payment_ids':[(6,0, payment_exist.ids)]})
                            break
                if cfdi_type=='SE':
                    for uu in [uuid,uuid.lower(),uuid.upper()]:
                        invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom','=',uu),('move_type','=','in_refund'), ('company_id','=',self.id)],limit=1)
                        if invoice_exist:
                            vals.update({'creado_en_odoo' : True,'invoice_ids':[(6,0, invoice_exist.ids)]})
                            break
                else:
                    for uu in [uuid,uuid.lower(),uuid.upper()]:
                        invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom','=',uu),('move_type','=','in_invoice'), ('company_id','=',self.id)],limit=1)
                        if invoice_exist:
                            vals.update({'creado_en_odoo' : True,'invoice_ids':[(6,0, invoice_exist.ids)]})
                            break
                attachment_obj.create(vals)

        #Customer
        if invoice_content_emisor:
            uuids = list(invoice_content_emisor.keys())
            attachments = attachment_obj.sudo().search([('cfdi_uuid','in',uuids), ('company_id', '=', self.id)])
            exist_uuids = attachments.mapped('cfdi_uuid')
            for uuid,data in invoice_content_emisor.items():
                if uuid in exist_uuids:
                    continue
                values = data[0]
                xml_content = data[1]
                #tree = etree.fromstring(xml_content)
                if b'xmlns:schemaLocation' in xml_content:
                    xml_content = xml_content.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
                elif b'Ya no puedes descargar' in xml_content:
                    _logger.info('Ya no puedes descargar más documentos. Por seguridad únicamente se permite descargar un máximo de 2,000 archivos por día.')
                    continue
                try:
                    tree = etree.fromstring(xml_content)
                except Exception as e:
                    self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
                                             {'title': "Error", 'message': "No pudo leer un XML descargado", 'sticky': False, 'warning': True})
                    _logger.error('error emitida schema: ' + str(e))
                    continue
                try:
                    ns = tree.nsmap
                    ns.update({'re': 'http://exslt.org/regular-expressions'})
                except Exception:
                    ns = {'re': 'http://exslt.org/regular-expressions'}
                xml_content = base64.b64encode(xml_content)

                ns_url = ns.get('cfdi')
                root_tag = 'Comprobante'
                if ns_url:
                    root_tag = '{'+ns_url+'}Comprobante'
                #Validation to only admit CFDI
                if tree.tag != root_tag:
                    #Invalid invoice file.
                    continue
                try:
                    emisor_elements = tree.xpath("//*[re:test(local-name(), 'Receptor','i')]", namespaces=ns)
                except Exception:
                    _logger.info("No encontró al receptor")
                e_rfc, e_name, r_folio = '', '', ''
                if emisor_elements:
                    attrib_dict = CaselessDictionary(dict(emisor_elements[0].attrib))
                    e_rfc = attrib_dict.get('rfc') #emisor_elements[0].get(attrib_dict.get('rfc'))
                    e_name = attrib_dict.get('nombre') #emisor_elements[0].get(attrib_dict.get('nombre'))
                r_folio = str(tree.get("Serie")) + str(tree.get("Folio")) #receptor_elements[0].get(attrib_dict.get('nombre'))
                
                cfdi_version = tree.get("Version",'4.0')
                if cfdi_version=='4.0':
                    NSMAP.update({'cfdi':'http://www.sat.gob.mx/cfd/4', 'pago20': 'http://www.sat.gob.mx/Pagos20',})
                else:
                    NSMAP.update({'cfdi':'http://www.sat.gob.mx/cfd/3', 'pago10': 'http://www.sat.gob.mx/Pagos',})
                    
                    
                cfdi_type = tree.get("TipoDeComprobante",'I')
                if cfdi_type not in ['I','E','P','N','T']:
                    cfdi_type = 'I'

                monto_total = 0
                if cfdi_type=='P':
                        complemento = tree.find('cfdi:Complemento', NSMAP)
                        if cfdi_version == '4.0':
                           pagos = complemento.find('pago20:Pagos', NSMAP)
                           pago = pagos.find('pago20:Totales', NSMAP)
                           monto_total = pago.attrib['MontoTotalPagos']
                        else:
                           pagos = complemento.find('pago10:Pagos', NSMAP)
                           try:
                              pago = pagos.find('pago10:Pago',NSMAP)
                              monto_total = pago.attrib['Monto']
                           except Exception as e:
                              for payment in pagos.find('pago10:Pago',NSMAP):
                                  monto_total += float(payment.attrib['Monto'])
                else:
                    monto_total = values.get('total',0.0)

                filename = uuid + '.xml' # values.get('emisor')[:10]+'_'+values.get('rfc_emisor')
                vals = dict(
                        name=filename,
                        store_fname=filename,
                        type='binary',
                        datas=xml_content,
                        cfdi_uuid=uuid,
                        cfdi_type=cfdi_type,
                        company_id=self.id,
                        rfc_tercero = e_rfc,
                        nombre_tercero = e_name,
                        serie_folio = r_folio,
                        cfdi_total = monto_total,
                    )
                if values.get('date_cfdi'):
                    vals.update({'date_cfdi' : values.get('date_cfdi').strftime(DEFAULT_SERVER_DATE_FORMAT)})

                if cfdi_type=='P':
                    for uu in [uuid,uuid.lower(),uuid.upper()]:
                        payment_exist = payment_obj.search([('l10n_mx_edi_cfdi_uuid_cusom','=',uu),('payment_type','=','inbound'), ('company_id','=',self.id)],limit=1)
                        if payment_exist:
                            vals.update({'creado_en_odoo' : True,'payment_ids':[(6,0, payment_exist.ids)]})
                            break
                if cfdi_type=='E':
                    for uu in [uuid,uuid.lower(),uuid.upper()]:
                        invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom','=',uu),('move_type','=','out_refund'), ('company_id','=',self.id)],limit=1)
                        if invoice_exist:
                            vals.update({'creado_en_odoo' : True,'payment_ids':[(6,0, invoice_exist.ids)]})
                            break
                else:
                    for uu in [uuid,uuid.lower(),uuid.upper()]:
                        invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom','=',uu),('move_type','=','out_invoice'), ('company_id','=',self.id)],limit=1)
                        if invoice_exist:
                            vals.update({'creado_en_odoo' : True,'invoice_ids':[(6,0, invoice_exist.ids)]})
                            break

                attachment_obj.create(vals)
        self.write({'last_cfdi_fetch_date':today.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return
