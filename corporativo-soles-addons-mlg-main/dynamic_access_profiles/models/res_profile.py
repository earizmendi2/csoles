# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResProfile(models.Model):
    _name = 'res.profile'
    _description = 'User Profile for Field Control'
    _order = 'name'
    _parent_name = 'parent_profile_id'
    _parent_store = True

    name = fields.Char(string='Profile Name', required=True)
    description = fields.Char(string='Profile Description', required=True)
    parent_profile_id = fields.Many2one(
        'res.profile',
        string='Parent Profile',
        index=True,
        ondelete='restrict',
        domain="[('id', '!=', id)]",
        help='Informational hierarchy only. Rules are not inherited.',
    )
    child_profile_ids = fields.One2many(
        'res.profile', 'parent_profile_id', string='Child Profiles'
    )
    parent_path = fields.Char(index=True)
    field_ids = fields.One2many('res.profile.field', 'profile_id', string='Fields to Control')
    field_m2x_ids = fields.One2many('res.profile.field.m2x', 'profile_id', string='M2O and M2M Control')    
    model_access_ids = fields.One2many(
        'res.profile.model.access',
        'profile_id',
        string='Model Configurations',
    )
    group_ids = fields.Many2many('res.groups', store=True, string='Groups', help='Groups that users in this profile will have access to')
    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', string="Menus to hide",
        store=True, help='Select the menus or submenus that should be hidden for users of this profile')
    count_users = fields.Integer(compute='_compute_count_users', string='Users', store=True)
    user_ids = fields.Many2many(
        'res.users',
        'res_profile_res_users_rel',
        'res_profile_id',
        'res_users_id',
        string='Users',
    )
    group_count = fields.Integer(compute='_compute_dashboard_counts', string='Groups')
    field_rule_count = fields.Integer(compute='_compute_dashboard_counts', string='Field Rules')
    related_rule_count = fields.Integer(compute='_compute_dashboard_counts', string='Related Field Rules')
    hidden_menu_count = fields.Integer(compute='_compute_dashboard_counts', string='Hidden Menus')
    model_count = fields.Integer(compute='_compute_dashboard_counts', string='Models')
    conditional_rule_count = fields.Integer(
        compute='_compute_dashboard_counts', string='Conditional Rules'
    )
    button_rule_count = fields.Integer(
        compute='_compute_dashboard_counts', string='Hidden Buttons'
    )
    action_rule_count = fields.Integer(
        compute='_compute_dashboard_counts', string='Hidden Actions'
    )
    color = fields.Integer(string='Color')
    active = fields.Boolean(default=True)

    @api.constrains('parent_profile_id')
    def _check_profile_hierarchy(self):
        if not self._check_recursion():
            raise ValidationError(
                _('A profile cannot be a parent of itself or its ancestors.')
            )

    @api.depends(
        'group_ids', 'field_ids', 'field_ids.is_conditional',
        'field_m2x_ids', 'hide_menu_ids', 'model_access_ids',
        'model_access_ids.button_rule_ids',
        'model_access_ids.action_rule_ids',
    )
    def _compute_dashboard_counts(self):
        for profile in self:
            profile.group_count = len(profile.group_ids)
            profile.field_rule_count = len(profile.field_ids)
            profile.related_rule_count = len(profile.field_m2x_ids)
            profile.hidden_menu_count = len(profile.hide_menu_ids)
            profile.model_count = len(profile.model_access_ids)
            profile.conditional_rule_count = len(
                profile.field_ids.filtered('is_conditional')
            )
            profile.button_rule_count = sum(
                profile.model_access_ids.mapped('button_rule_count')
            )
            profile.action_rule_count = sum(
                profile.model_access_ids.mapped('action_rule_count')
            )

    @api.depends('user_ids')
    def _compute_count_users(self):
        for record in self:
            record.count_users = len(record.user_ids) if record.user_ids else 0

    def _get_all_implied_groups(self, groups, seen=None):
        """ Devuelve todos los grupos implícitos de los grupos dados. """
        if not seen:
            seen = self.env['res.groups']

        result = self.env['res.groups']

        for group in groups:
            if group in seen:
                continue

            seen |= group
            result |= group.implied_ids
            result |= self._get_all_implied_groups(group.implied_ids, seen)

        return result

    def _get_groups_to_remove(self, previous_groups):
        """Return profile groups that depend on a manually removed group."""
        self.ensure_one()
        manually_removed = previous_groups - self.group_ids
        if not manually_removed:
            return self.env['res.groups']

        groups_to_remove = self.env['res.groups']
        required_groups = manually_removed

        while True:
            dependent_groups = (self.group_ids - groups_to_remove).filtered(
                lambda group: bool(
                    self._get_all_implied_groups(group) & required_groups
                )
            )
            if not dependent_groups:
                break
            groups_to_remove |= dependent_groups
            required_groups |= dependent_groups

        return groups_to_remove

    def write(self, vals):
        """Sobrescribimos write para asegurar implied groups y limpiar cache si cambian menús."""
        previous_groups = {
            profile.id: profile.group_ids
            for profile in self
        } if 'group_ids' in vals else {}

        res = super(ResProfile, self).write(vals)

        if 'hide_menu_ids' in vals:
            self.env.registry.clear_cache('default', 'templates')

        if 'group_ids' in vals:
            for profile in self:
                profile.invalidate_recordset(['group_ids'])
                groups_to_remove = profile._get_groups_to_remove(
                    previous_groups[profile.id]
                )
                if groups_to_remove:
                    super(ResProfile, profile).write({
                        'group_ids': [(3, group.id) for group in groups_to_remove],
                    })
                    profile.invalidate_recordset(['group_ids'])

                if profile.group_ids:
                    profile._update_implied_groups()
        else:
            for profile in self:
                if profile.group_ids:
                    profile._update_implied_groups()

        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribimos create para asegurar implied groups."""
        profiles = super(ResProfile, self).create(vals_list)

        for profile in profiles:
            if profile.group_ids:
                profile._update_implied_groups()

        return profiles

    def copy(self, default=None):
        """Clone profile configuration without assigning users to the clone."""
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('name', _('%s (copy)') % self.name)
        default.setdefault('group_ids', [(6, 0, self.group_ids.ids)])
        default.setdefault(
            'hide_menu_ids', [(6, 0, self.hide_menu_ids.ids)]
        )
        default.setdefault(
            'model_access_ids',
            [
                (0, 0, {
                    'model_id': config.model_id.id,
                    'apply_form': config.apply_form,
                    'apply_list': config.apply_list,
                    'apply_kanban': config.apply_kanban,
                    'disable_create': config.disable_create,
                    'disable_edit': config.disable_edit,
                    'disable_delete': config.disable_delete,
                    'field_ids': [
                        (0, 0, {
                            'field_id': rule.field_id.id,
                            'is_required': rule.is_required,
                            'is_invisible': rule.is_invisible,
                            'is_readonly': rule.is_readonly,
                            'is_conditional': rule.is_conditional,
                            'condition_domain': rule.condition_domain,
                        })
                        for rule in config.field_ids
                    ],
                    'field_m2x_ids': [
                        (0, 0, {
                            'field_id': rule.field_id.id,
                            'no_open': rule.no_open,
                            'no_create': rule.no_create,
                            'no_create_edit': rule.no_create_edit,
                            'no_quick_create': rule.no_quick_create,
                        })
                        for rule in config.field_m2x_ids
                    ],
                    'button_rule_ids': [
                        (0, 0, {
                            'button_id': rule.button_id.id,
                            'hide': rule.hide,
                        })
                        for rule in config.button_rule_ids
                    ],
                    'action_rule_ids': [
                        (0, 0, {
                            'action_id': rule.action_id.id,
                            'hide': rule.hide,
                        })
                        for rule in config.action_rule_ids
                    ],
                })
                for config in self.model_access_ids
            ],
        )
        return super().copy(default)
    
    def _update_implied_groups(self):
        """ Actualiza los grupos implícitos para este perfil. """
        for profile in self:
            if profile.group_ids:
                implied = profile._get_all_implied_groups(profile.group_ids)
                new_groups = profile.group_ids | implied
                if new_groups != profile.group_ids:
                    profile.group_ids = new_groups
    
    def action_update_profile_users(self):
        """ Acción para actualizar los usuarios asociados a este perfil. """
        total_users = 0
        for profile in self:
            users = self.env['res.users'].search([
                ('profile_ids', 'in', profile.id)
            ])
            for user in users:
                user._update_groups_from_profiles()
            total_users += len(users)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Profiles Updated'),
                'message': _('Successfully updated %s users.') % total_users,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_users(self):
        self.ensure_one()

        return {
            'name': _('Users with Profile: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('base.view_users_tree').id, 'list'),
                (self.env.ref('base.view_users_form').id, 'form'),
            ],
            'domain': [('profile_ids', 'in', [self.id])],
            'context': {
                'default_profile_ids': [(4, self.id)],
            },
        }

    def get_profile_org_chart(self):
        self.ensure_one()

        # The chart is informational and must not be trimmed by the current
        # user's profile rules. Five levels means the current node plus four
        # descendant generations.
        root = self.sudo()

        def prepare(profile, depth=0):
            values = {
                'id': profile.id,
                'name': profile.name,
                'description': profile.description or '',
                'color': profile.color,
                'user_count': profile.count_users,
                'child_count': len(profile.child_profile_ids),
            }
            values['children'] = (
                [prepare(child, depth + 1) for child in profile.child_profile_ids]
                if depth < 4 else []
            )
            return values

        managers = self.env['res.profile']
        current = root.parent_profile_id
        while current and current not in managers and len(managers) < 5:
            managers |= current
            current = current.parent_profile_id

        return {
            'current': prepare(root),
            'managers': [prepare(profile, 4) for profile in reversed(managers)],
        }
