from odoo import _, api, fields, models

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        # OVERRIDE
        cfdi_values = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        total_tax_details_transferred = 0
        for tax_detail_vals in cfdi_values['tax_details_transferred']['tax_details'].values():
            details = tax_detail_vals['group_tax_details']
            tax_detail_vals['tax_amount'] = sum(
                round(x['tax_amount'], cfdi_values['currency_precision']) for x in details)
            tax_detail_vals['tax_amount_currency'] = sum(round(
                x['tax_amount_currency'], cfdi_values['currency_precision']) for x in details)
            total_tax_details_transferred += cfdi_values['balance_multiplicator'] * \
                tax_detail_vals['tax_amount_currency']
            
        print ("TotalTax----------+", round(total_tax_details_transferred, cfdi_values['currency_precision']))
        
        cfdi_values.update({
            'total_tax_details_transferred': round(total_tax_details_transferred, cfdi_values['currency_precision'])
        })

        subtotal = round(
            cfdi_values['total_price_subtotal_before_discount'], cfdi_values['currency_precision'])
        discount = round(cfdi_values['total_price_discount'], cfdi_values['currency_precision']
                         ) if not cfdi_values['record'].currency_id.is_zero(cfdi_values['total_price_discount']) else 0
        cfdi_values.update({
            'cfdi_total': subtotal+total_tax_details_transferred-discount
        })

        return cfdi_values
