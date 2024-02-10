# -*- coding: utf-8 -*-

{
    'name':         'Administrador de documentos Digitales Complemento',
    'version': '16.03',
    'description':  ''' 
                    Complemento para la descarga de los XML, junta serie y folio
                    ''',
    'category':     'Accounting',
    'author':       'Ivan Legarda',
    'website':      '',
    'depends':      [
                    'account','l10n_mx_edi','sale_management','purchase','account_accountant'
                    ],
    'data':         [
                    'security/ir.model.access.csv',
                    'security/l10n_mx_edi_esignature.xml',
                    'data/cron_data.xml',

                    'views/ir_attachment_view.xml',
                    'views/res_config_settings_view.xml',
                    #'views/templates.xml',
                    'views/res_company_view.xml',
                    'views/esignature_view.xml',
                    'views/account_move_view.xml',
                    'views/account_tax_view.xml',

                    'wizard/cfdi_invoice.xml',
                    'wizard/import_invoice_process_message.xml',
                    'wizard/reconcile_vendor_cfdi_xml_bill.xml',
                    'wizard/xml_invoice_reconcile_view.xml',
                    'wizard/descarga_x_dia_wizard.xml',
                    'wizard/attach_xmls_wizard_view.xml',
                    'report/report_facturas_de_clientes_or_proveedores.xml',
                    'report/payment_report_from_xml.xml',
                    ],
    'assets': {
        'web.assets_backend': [
            'rodo_sat_sync_mx/static/src/js/**/*',
            'rodo_sat_sync_mx/static/src/xml/list_buttons.xml',
            'rodo_sat_sync_mx/static/src/css/**/*',
            'rodo_sat_sync_mx/static/src/xml/*.xml',
        ],
        'web.assets_qweb': [
            'rodo_sat_sync_mx/static/src/xml/*.xml',
        ],
    },
    'application':  False,
    'installable':  True,
    'license': 'AGPL-3',
}
