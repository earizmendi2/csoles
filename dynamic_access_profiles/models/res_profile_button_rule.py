from odoo import api, fields, models


class ResProfileViewButton(models.Model):
    _name = 'res.profile.view.button'
    _description = 'Discovered View Button'
    _order = 'label, view_id'
    _rec_name = 'display_label'

    label = fields.Char(required=True)
    model_id = fields.Many2one('ir.model', required=True, ondelete='cascade')
    view_id = fields.Many2one('ir.ui.view', required=True, ondelete='cascade')
    view_type = fields.Selection(
        [('form', 'Form'), ('list', 'List'), ('kanban', 'Kanban')],
        required=True,
    )
    technical_name = fields.Char(required=True)
    button_type = fields.Selection(
        [('object', 'Object Method'), ('action', 'Action')], required=True
    )
    is_smart_button = fields.Boolean(string='Smart Button')
    group_expression = fields.Char()
    display_label = fields.Char(compute='_compute_display_label', store=True)
    technical_key = fields.Char(required=True, index=True)

    _sql_constraints = [
        ('technical_key_unique', 'UNIQUE(technical_key)',
         'The discovered button must be unique.'),
    ]

    @api.depends('label', 'view_id', 'view_type', 'is_smart_button')
    def _compute_display_label(self):
        for button in self:
            kind = 'Smart button' if button.is_smart_button else button.view_type.title()
            button.display_label = f'{button.label} — {kind} — {button.view_id.name}'


class ResProfileButtonRule(models.Model):
    _name = 'res.profile.button.rule'
    _description = 'Profile Button Restriction'

    profile_model_id = fields.Many2one(
        'res.profile.model.access', required=True, ondelete='cascade'
    )
    model_id = fields.Many2one(related='profile_model_id.model_id')
    button_id = fields.Many2one(
        'res.profile.view.button', string='Button', required=True, ondelete='cascade'
    )
    hide = fields.Boolean(default=True, required=True)

    _sql_constraints = [
        ('button_per_configuration', 'UNIQUE(profile_model_id, button_id)',
         'This button is already restricted for the model configuration.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache('default', 'templates')
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache('default', 'templates')
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache('default', 'templates')
        return result
