from odoo import _, api, fields, models
import logging
_logger = logging.getLogger(__name__)

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'               

    def _l10n_mx_edi_get_payment_cfdi_values(self, invoice):      
        
        def trunc_n(n,d):
            dp = repr(n).find('.')
            if dp == -1:  
                return int(n) 
            return float(repr(n)[:dp+d+1])                  
            
        
        # OVERRIDE THIS FUNCTION
        vals = super()._l10n_mx_edi_get_payment_cfdi_values(invoice)               
        vals['trunc_monto'] = trunc_n(vals.get('amount',0),2)
        for invoice_val in vals['invoice_vals_list']:            
            invoice_val['trunc_saldo_ant'] = trunc_n(invoice_val.get('amount_before_paid',0),2)        
            _logger.info('trunc_saldo_ant %s'%invoice_val['trunc_saldo_ant'])
            invoice_val['trunc_pagado'] = trunc_n(invoice_val.get('amount_paid',0),2)
            _logger.info('trunc_pagado %s'%invoice_val['trunc_pagado'])
            invoice_val['trunc_insoluto'] = trunc_n(invoice_val['trunc_saldo_ant'] - invoice_val['trunc_pagado'],2)
            _logger.info('trunc_insoluto %s'%invoice_val['trunc_insoluto'])
        return vals
        


    

  