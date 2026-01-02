from odoo import models, _
from odoo.exceptions import UserError


class AIThread(models.Model):
    _inherit = "ai.thread"

    def _get_tools_spec_gemini(self):
        return self._get_tools_spec()

    def _do_request_gemini(self, message):
        """Handle Gemini API request"""
        self.ensure_one()
        config = self.config_id.sudo()
        client = config._get_ai_client()

        # Add system context if exists
        system_instruction = None
        if thread_context := self._get_thread_context():
            system_instruction = thread_context

        # Add conversation history
        messages = self._prepare_message_history_gemini(self.message_ids)

        gemini_config = {
            "system_instruction": system_instruction,
            "temperature": config.temperature,
            "max_output_tokens": config.max_tokens,
        }
        if tools_spec := self._get_tools_spec_gemini():
            gemini_config["tools"] = [{"function_declarations": tools_spec}]

        try:
            response = client.models.generate_content(
                model=config.model,
                contents=messages,
                config=gemini_config,
            )
            return response

        except Exception as e:
            raise UserError(_("Gemini API Error: %s") % str(e))

    def _prepare_message_history_gemini(self, messages):
        self.ensure_one()
        message_history = []
        for msg in messages:
            message_history.append(msg._prepare_message_content_gemini())
        return message_history

    def _dump_response_json_gemini(self, response):
        self.ensure_one()
        return response.model_dump_json(indent=2)

    def _parse_response_tool_gemini(self, response):
        func_call = response.function_calls and response.function_calls[0] or False
        if func_call:
            func_call = func_call.model_dump()
        return func_call

    def _execute_tool_gemini(self, func_call):
        return self._run_tool(func_call['name'], **func_call['args'])

    def _parse_response_text_gemini(self, response):
        """Parse Gemini response content"""
        try:
            return response.text
        except ValueError:
            return ""
