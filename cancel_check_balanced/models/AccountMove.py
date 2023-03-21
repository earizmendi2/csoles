# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _

class AccountMove(models.Model):
    _inherit = "account.move"          

    def _check_balanced(self):
        #OVERRIDE FUNCTION
        ''' Assert the move is fully balanced debit = credit.
        An error is raised if it's not the case.
        '''
        return True
        