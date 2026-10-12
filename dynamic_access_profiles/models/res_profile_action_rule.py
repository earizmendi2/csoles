from odoo import api, fields, models


class ResProfileBoundAction(models.Model):
    _name = 'res.profile.bound.action'
    _description = 'Discovered Bound Action'
    _order = 'name'

    name = fields.Char(required=True)
    model_id = fields.Many2one('ir.model', required=True, ondelete='cascade')
    action_id = fields.Integer(required=True)
    action_model = fields.Char(required=True)
    binding_type = fields.Selection(
        [('action', 'Action'), ('report', 'Print')], required=True
    )
    technical_key = fields.Char(required=True, index=True)

    _sql_constraints = [
        ('technical_key_unique', 'UNIQUE(technical_key)',
         'The discovered bound action must be unique.'),
    ]


class ResProfileActionRule(models.Model):
    _name = 'res.profile.action.rule'
    _description = 'Profile Bound Action Restriction'

    profile_model_id = fields.Many2one(
        'res.profile.model.access', required=True, ondelete='cascade'
    )
    model_id = fields.Many2one(related='profile_model_id.model_id')
    action_id = fields.Many2one(
        'res.profile.bound.action', string='Action', required=True, ondelete='cascade'
    )
    hide = fields.Boolean(default=True, required=True)

    _sql_constraints = [
        ('action_per_configuration', 'UNIQUE(profile_model_id, action_id)',
         'This action is already restricted for the model configuration.'),
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


class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    @api.model
    def get_bindings(self, model_name):
        bindings = super().get_bindings(model_name)
        if self.env.su:
            return bindings
        rules = self.env.user.sudo().profile_ids.mapped(
            'model_access_ids.action_rule_ids'
        ).filtered(
            lambda rule: rule.hide and rule.model_id.model == model_name
        )
        hidden = {
            (rule.action_id.action_id, rule.action_id.action_model)
            for rule in rules
        }
        action_ids = {
            action.get('id')
            for actions in bindings.values()
            for action in actions
            if action.get('id')
        }
        action_types = {
            action['id']: action['type']
            for action in self.sudo().browse(action_ids).read(['type'])
        }
        return {
            category: [
                action for action in actions
                if (
                    action.get('id'), action_types.get(action.get('id'))
                ) not in hidden
            ]
            for category, actions in bindings.items()
        }
