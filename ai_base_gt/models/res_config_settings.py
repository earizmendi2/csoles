from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rag_server_url = fields.Char(string="RAG Server URL",
                                 config_parameter='ai_base_gt.rag_server_url',
                                 default='http://localhost:8000')
    rag_server_token = fields.Char(string="RAG Server Token",
                                   config_parameter='ai_base_gt.rag_server_token')
