from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    profile_ids = fields.Many2many(
        'res.profile',
        'res_profile_res_users_rel',
        'res_users_id',
        'res_profile_id',
        string='Profiles',
    )

    def _get_hide_menus(self):
        menus = []
        hide_menus = self.profile_ids.mapped('hide_menu_ids')
        
        if hide_menus:
            menus = hide_menus.ids
        return menus

    def _update_groups_from_profiles(self):
        self.ensure_one()

        groups = self.profile_ids.mapped('group_ids')
        if not groups:
            return

        all_groups = groups | groups.mapped('implied_ids')
        self.groups_id = [(6, 0, all_groups.ids)]

    
    @api.model_create_multi
    def create(self, vals_list):
        """ Sobrescribimos create para aplicar la lógica al crear un usuario. """
        user = super(ResUsers, self).create(vals_list)
        for vals in vals_list:
            if 'profile_ids' in vals:
                user._update_groups_from_profiles()
        return user

    def write(self, vals):
        """ Sobrescribimos write para actualizar grupos cuando cambian los perfiles. """
        res = super(ResUsers, self).write(vals)
        if 'profile_ids' in vals:
            self._update_groups_from_profiles()
            self.env.registry.clear_cache('default', 'templates')
        return res

    def get_profile_context(self):
        return {
            'profile_ids': self.profile_ids.ids,
        }

    def get_context(self):
        context = super(ResUsers, self).get_context()
        context.update(self.get_profile_context())
        return context

    @api.model
    def get_profile_fields(self):
        """
        Retorna un diccionario con dos listas de campos: 'normal_fields' y 'm2x_fields'.
        Cada lista se obtiene de funciones dedicadas a procesar los respectivos campos.
        """
        normal_fields = self._get_normal_fields()
        m2x_fields = self._get_m2x_fields()

        return {
            'normal_fields': normal_fields,
            'm2x_fields': m2x_fields
        }

    @api.model
    def _get_normal_fields(self):
        """
        Procesa y retorna la lista de campos normales, aplicando prioridad según los perfiles.
        """
        current_user = self.env.user
        field_ids = current_user.profile_ids.mapped('field_ids').filtered(
            lambda rule: not rule.is_conditional
        )

        field_dict = {}
        for field in field_ids:
            key = (field.field_id.name, field.model_id.model)
            if key not in field_dict:
                field_dict[key] = {
                    'field_name': field.field_id.name,
                    'model_name': field.model_id.model,
                    'is_required': field.is_required,
                    'is_invisible': field.is_invisible,
                    'is_readonly': field.is_readonly,
                }
            else:
                existing_field = field_dict[key]
                if field.is_required:
                    existing_field['is_required'] = True
                    existing_field['is_invisible'] = False
                    existing_field['is_readonly'] = False
                elif field.is_invisible and not existing_field['is_required']:
                    existing_field['is_invisible'] = True
                    existing_field['is_readonly'] = False
                elif field.is_readonly and not existing_field['is_required'] and not existing_field['is_invisible']:
                    existing_field['is_readonly'] = True

        normal_fields = list(field_dict.values())
        return normal_fields

    @api.model
    def _get_m2x_fields(self):
        """
        Procesa y retorna la lista de campos de tipo muchos a uno/muchos a muchos, aplicando prioridad según los perfiles.
        """
        current_user = self.env.user
        field_m2x_ids = current_user.profile_ids.mapped('field_m2x_ids')

        m2x_field_dict = {}
        for field in field_m2x_ids:
            key = (field.field_id.name, field.model_id.model)
            if key not in m2x_field_dict:
                m2x_field_dict[key] = {
                    'field_name': field.field_id.name,
                    'model_name': field.model_id.model,
                    'no_open': field.no_open,
                    'no_create': field.no_create,
                    'no_quick_create': field.no_quick_create,
                    'no_create_edit': field.no_create_edit,
                }
            else:
                existing_field = m2x_field_dict[key]
                existing_field['no_open'] = field.no_open or existing_field['no_open']
                existing_field['no_create'] = field.no_create or existing_field['no_create']
                existing_field['no_quick_create'] = field.no_quick_create or existing_field['no_quick_create']
                existing_field['no_create_edit'] = field.no_create_edit or existing_field['no_create_edit']

        m2x_fields = list(m2x_field_dict.values())
        return m2x_fields
