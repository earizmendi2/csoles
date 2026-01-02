from google import genai
from odoo import fields, models, _
from odoo.exceptions import UserError


class AIConfig(models.Model):
    _inherit = 'ai.config'

    type = fields.Selection(
        selection_add=[('gemini', 'Gemini')],
        ondelete={'gemini': 'cascade'}
    )

    def _get_default_model(self):
        if self.type == 'gemini':
            return 'gemini-2.5-flash'
        return super()._get_default_model()

    def _get_gemini_client(self):
        if not self.api_key:
            raise UserError(_("Gemini API key is not configured"))
        return genai.Client(api_key=self.api_key)
