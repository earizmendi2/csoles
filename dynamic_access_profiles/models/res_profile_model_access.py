from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResProfileModelAccess(models.Model):
    _name = 'res.profile.model.access'
    _description = 'Profile Model Configuration'
    _order = 'model_id'

    profile_id = fields.Many2one(
        'res.profile', string='Profile', required=True, ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    technical_name = fields.Char(
        related='model_id.model', string='Technical Name'
    )
    apply_form = fields.Boolean(string='Form', default=True)
    apply_list = fields.Boolean(string='List')
    apply_kanban = fields.Boolean(string='Kanban')
    disable_create = fields.Boolean(string='Disable Create')
    disable_edit = fields.Boolean(string='Disable Edit')
    disable_delete = fields.Boolean(string='Disable Delete')
    field_ids = fields.One2many(
        'res.profile.field', 'profile_model_id', string='Field Properties'
    )
    field_m2x_ids = fields.One2many(
        'res.profile.field.m2x',
        'profile_model_id',
        string='Related Field Actions',
    )
    button_rule_ids = fields.One2many(
        'res.profile.button.rule', 'profile_model_id', string='Hidden Buttons'
    )
    available_button_ids = fields.Many2many(
        'res.profile.view.button', compute='_compute_available_button_ids'
    )
    action_rule_ids = fields.One2many(
        'res.profile.action.rule', 'profile_model_id', string='Hidden Actions'
    )
    field_count = fields.Integer(compute='_compute_rule_counts')
    related_field_count = fields.Integer(compute='_compute_rule_counts')
    button_rule_count = fields.Integer(compute='_compute_rule_counts')
    action_rule_count = fields.Integer(compute='_compute_rule_counts')
    view_scope = fields.Char(compute='_compute_summaries')
    restriction_summary = fields.Char(compute='_compute_summaries')

    @api.depends(
        'field_ids', 'field_m2x_ids', 'button_rule_ids', 'action_rule_ids'
    )
    def _compute_rule_counts(self):
        for config in self:
            config.field_count = len(config.field_ids)
            config.related_field_count = len(config.field_m2x_ids)
            config.button_rule_count = len(config.button_rule_ids)
            config.action_rule_count = len(config.action_rule_ids)

    @api.depends('model_id', 'profile_id.group_ids')
    def _compute_available_button_ids(self):
        catalog = self.env['res.profile.view.button']
        for config in self:
            buttons = catalog.search([('model_id', '=', config.model_id.id)])
            config.available_button_ids = buttons.filtered(
                lambda button: config._is_group_expression_allowed(
                    button.group_expression
                )
            )

    def _is_group_expression_allowed(self, expression):
        self.ensure_one()
        if not expression:
            return True
        groups = self.profile_id.group_ids
        groups |= self.profile_id._get_all_implied_groups(groups)
        xmlids = set(groups.get_external_id().values())
        tokens = [token.strip() for token in expression.split(',') if token.strip()]
        positives = [token for token in tokens if not token.startswith('!')]
        negatives = [token[1:] for token in tokens if token.startswith('!')]
        return not (xmlids & set(negatives)) and (
            not positives or bool(xmlids & set(positives))
        )

    def action_discover_buttons(self):
        self.ensure_one()
        catalog = self.env['res.profile.view.button'].sudo()
        views = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self.model_id.model),
            ('type', 'in', ['form', 'list', 'kanban']),
            ('mode', '=', 'primary'),
            ('active', '=', True),
        ])
        discovered = 0
        for view in views:
            arch = view._get_combined_arch()
            for node in arch.xpath('.//button[@name]'):
                button_type = node.get('type', 'object')
                if button_type not in {'object', 'action'}:
                    continue
                technical_name = node.get('name')
                is_smart = 'oe_stat_button' in node.get('class', '').split()
                key = ':'.join([
                    str(self.model_id.id), str(view.id), view.type,
                    button_type, technical_name, str(int(is_smart)),
                ])
                values = {
                    'label': node.get('string') or technical_name,
                    'model_id': self.model_id.id,
                    'view_id': view.id,
                    'view_type': view.type,
                    'technical_name': technical_name,
                    'button_type': button_type,
                    'is_smart_button': is_smart,
                    'group_expression': node.get('groups'),
                    'technical_key': key,
                }
                existing = catalog.search([('technical_key', '=', key)], limit=1)
                existing.write(values) if existing else catalog.create(values)
                discovered += 1
        self.invalidate_recordset(['available_button_ids'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Buttons refreshed'),
                'message': _('%s buttons were discovered.') % discovered,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_discover_actions(self):
        self.ensure_one()
        catalog = self.env['res.profile.bound.action'].sudo()
        bindings = self.env['ir.actions.actions'].sudo().get_bindings(
            self.model_id.model
        )
        discovered = 0
        for category, actions in bindings.items():
            if category not in {'action', 'report'}:
                continue
            for action in actions:
                action_id = action.get('id')
                if not action_id:
                    continue
                # Odoo 19 intentionally omits ``type`` from get_bindings().
                # Read it from the common action table so every bound action
                # can be catalogued and subsequently identified reliably.
                action_model = self.env['ir.actions.actions'].sudo().browse(
                    action_id
                ).type
                if not action_model:
                    continue
                key = f'{self.model_id.id}:{action_model}:{action_id}'
                values = {
                    'name': action.get('name') or key,
                    'model_id': self.model_id.id,
                    'action_id': action_id,
                    'action_model': action_model,
                    'binding_type': category,
                    'technical_key': key,
                }
                existing = catalog.search([('technical_key', '=', key)], limit=1)
                existing.write(values) if existing else catalog.create(values)
                discovered += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actions refreshed'),
                'message': _('%s actions were discovered.') % discovered,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.depends(
        'apply_form',
        'apply_list',
        'apply_kanban',
        'disable_create',
        'disable_edit',
        'disable_delete',
    )
    def _compute_summaries(self):
        for config in self:
            view_names = []
            if config.apply_form:
                view_names.append(_('Form'))
            if config.apply_list:
                view_names.append(_('List'))
            if config.apply_kanban:
                view_names.append(_('Kanban'))
            restriction_names = []
            if config.disable_create:
                restriction_names.append(_('Create'))
            if config.disable_edit:
                restriction_names.append(_('Edit'))
            if config.disable_delete:
                restriction_names.append(_('Delete'))
            config.view_scope = ', '.join(view_names) or _('No view restriction')
            config.restriction_summary = (
                ', '.join(restriction_names) or _('Field rules only')
            )

    @api.constrains(
        'apply_form',
        'apply_list',
        'apply_kanban',
        'disable_create',
        'disable_edit',
        'disable_delete',
    )
    def _check_view_scope(self):
        for rule in self:
            has_restriction = (
                rule.disable_create
                or rule.disable_edit
                or rule.disable_delete
            )
            has_view = rule.apply_form or rule.apply_list or rule.apply_kanban
            if has_restriction and not has_view:
                raise ValidationError(
                    _('Select at least one view for the restrictions.')
                )

    @api.constrains('profile_id', 'model_id')
    def _check_unique_model_per_profile(self):
        for rule in self:
            duplicate = self.search_count([
                ('profile_id', '=', rule.profile_id.id),
                ('model_id', '=', rule.model_id.id),
                ('id', '!=', rule.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "The model '%(model)s' is already configured for "
                    "the profile '%(profile)s'.",
                    model=rule.model_id.name,
                    profile=rule.profile_id.name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        self.env.registry.clear_cache('default', 'templates')
        return rules

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache('default', 'templates')
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache('default', 'templates')
        return result
