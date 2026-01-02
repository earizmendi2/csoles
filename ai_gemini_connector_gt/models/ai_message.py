import json
from google.genai.types import GenerateContentResponse

from odoo import models


class AIMessage(models.Model):
    _inherit = "ai.message"

    def _filter_legit_attachments(self):
        # Gemini currently supports images and PDFs.
        if self.thread_id.config_id.sudo().type == "gemini":
            return self.attachment_ids.filtered(
                lambda a: a.mimetype.startswith("image/") or a.mimetype == "application/pdf"
            )
        return super()._filter_legit_attachments()

    def _prepare_message_content_gemini(self):
        self.ensure_one()
        content = {
            'role': 'user' if self.message_type in ('prompt', 'system') else 'model',
            'parts': [],
        }

        if self.response:
            response = GenerateContentResponse.model_validate_json(self.response)
            content['parts'].extend(response.parts)
            return content

        if self.content:
            content['parts'].append({"text": self.content_full})

        if self.legit_attachment_ids:
            content['parts'].extend([{
                "inline_data": {
                    "mime_type": attachment.mimetype,
                    "data": attachment.datas.decode("utf-8"),
                }
            } for attachment in self.legit_attachment_ids])

        if self.func_result:
            prev_message = self.thread_id.message_ids.filtered(lambda m: m.id < self.id)[-1:]
            func_call = json.loads(prev_message.func_call or "{}")
            part = {
                "function_response": {
                    "id": func_call.get("id", None),
                    "name": func_call.get("name", None),
                    "response": {"result": json.loads(self.func_result)}
                }
            }
            content['parts'].append(part)
        # Keep for backward compatibility
        elif self.func_call:
            func_call = json.loads(self.func_call)
            part = {
                "function_call": func_call
            }
            content['parts'].append(part)
        # End of backward compatibility

        return content
