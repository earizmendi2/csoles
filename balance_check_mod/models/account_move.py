from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def _check_balanced(self):
        return True
    

            