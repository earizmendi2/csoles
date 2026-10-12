from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ResProfileFieldM2x(models.Model):
    _name = 'res.profile.field.m2x'
    _description = 'Profile Many2x Fields Access Control'
    
    profile_id = fields.Many2one('res.profile', string='Profile', required=True, ondelete='cascade')
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    profile_model_id = fields.Many2one(
        'res.profile.model.access',
        string='Model Configuration',
        ondelete='cascade',
        index=True,
    )
    technical_name = fields.Char(
        related='field_id.name',
        string='Technical Name',
    )
    
    field_id = fields.Many2one(
        'ir.model.fields', 
        string='Field', 
        required=True, 
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('readonly', '=', False), ('ttype', 'in', ['many2one', 'many2many'])]"
    )
    
    no_open = fields.Boolean(
        string="Can't External Link", 
        default=False, 
        help="Disable this to prevent showing the external link for records."
    )
    
    no_create = fields.Boolean(
        string="Can't Create", 
        default=False, 
        help="Disable this to prevent creating new records."
    )

    no_create_edit = fields.Boolean(
        string="Can't Create/Edit", 
        default=False, 
        help="Disable this to prevent creation and editing of new records"
    )

    no_quick_create = fields.Boolean(
        string="Can't Quick Create", 
        default=False, 
        help="Disable this to prevent quick creation of new records."
    )

    @api.model
    def _get_or_create_profile_model(self, profile_id, model_id):
        if not profile_id or not model_id:
            return self.env['res.profile.model.access']
        config_model = self.env['res.profile.model.access']
        config = config_model.search([
            ('profile_id', '=', profile_id),
            ('model_id', '=', model_id),
        ], limit=1)
        if not config:
            config = config_model.create({
                'profile_id': profile_id,
                'model_id': model_id,
                'disable_edit': False,
            })
        return config

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for values in vals_list:
            values = dict(values)
            config = self.env['res.profile.model.access'].browse(
                values.get('profile_model_id')
            )
            if config:
                values.update({
                    'profile_id': config.profile_id.id,
                    'model_id': config.model_id.id,
                })
            elif values.get('profile_id') and values.get('model_id'):
                config = self._get_or_create_profile_model(
                    values['profile_id'], values['model_id']
                )
                values['profile_model_id'] = config.id
            prepared_vals_list.append(values)
        return super().create(prepared_vals_list)

    def write(self, vals):
        if {'profile_model_id', 'profile_id', 'model_id'} & vals.keys():
            for rule in self:
                values = dict(vals)
                config = self.env['res.profile.model.access'].browse(
                    values.get('profile_model_id')
                )
                if config:
                    values.update({
                        'profile_id': config.profile_id.id,
                        'model_id': config.model_id.id,
                    })
                else:
                    config = self._get_or_create_profile_model(
                        values.get('profile_id', rule.profile_id.id),
                        values.get('model_id', rule.model_id.id),
                    )
                    values['profile_model_id'] = config.id
                super(ResProfileFieldM2x, rule).write(values)
            return True
        return super().write(vals)

    @api.onchange('profile_model_id')
    def _onchange_profile_model_id(self):
        if self.profile_model_id:
            self.profile_id = self.profile_model_id.profile_id
            self.model_id = self.profile_model_id.model_id

    @api.constrains('no_open', 'no_create', 'no_create_edit', 'no_quick_create')
    def _check_at_least_one_action_selected(self):
        """
        Validación para asegurar que al menos una de las acciones esté seleccionada.
        Si ninguna está seleccionada, arroja un error.
        """
        for record in self:
            if not (record.no_open or record.no_create or record.no_create_edit or record.no_quick_create):
                raise ValidationError(_("At least one action must be selected: 'Can't External Link', 'Can't Create', 'Can't Create/Edit', or 'Can't Quick Create'."))
    
    @api.constrains('profile_id', 'field_id')
    def _check_unique_field_in_profile(self):
        """ Evita que el mismo campo se repita dentro de un perfil. """
        for record in self:
            existing_field = self.search([
                ('profile_id', '=', record.profile_id.id),
                ('field_id', '=', record.field_id.id),
                ('id', '!=', record.id)
            ])
            if existing_field:
                raise ValidationError(
                    _("The field '%s' is already configured for the profile '%s'.",record.field_id.field_description,record.profile_id.name)
                )

    @api.constrains('profile_model_id', 'profile_id', 'model_id')
    def _check_profile_model_consistency(self):
        for rule in self.filtered('profile_model_id'):
            if (
                rule.profile_id != rule.profile_model_id.profile_id
                or rule.model_id != rule.profile_model_id.model_id
            ):
                raise ValidationError(_(
                    'The related field rule does not match its model '
                    'configuration.'
                ))
