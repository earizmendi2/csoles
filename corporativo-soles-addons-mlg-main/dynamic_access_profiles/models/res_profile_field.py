import ast

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResProfileField(models.Model):
    _name = 'res.profile.field'
    _description = 'Field Rules for Profile'

    profile_id = fields.Many2one('res.profile', string='Profile', required=True)
    model_id = fields.Many2one('ir.model',string='Model',ondelete='cascade',required=True)
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
        domain="[('model_id', '=', model_id), ('readonly', '=', False), '|', ('required', '=', False), ('ttype', 'in', ['integer', 'float', 'monetary'])]"
    )
    field_is_python_required = fields.Boolean(
        related='field_id.required',
        string='Required in Python',
    )
    field_type = fields.Selection(
        related='field_id.ttype',
        string='Field Type',
    )
    model_name = fields.Char(related='model_id.model', string='Model Name')
    is_conditional = fields.Boolean(string='Conditional')
    condition_domain = fields.Char(
        string='Apply When',
        default='[]',
        help='The field behavior is applied when the record matches this domain.',
    )

    is_required = fields.Boolean(string='Required', default=False)
    is_invisible = fields.Boolean(string='Invisible', default=False)
    is_readonly = fields.Boolean(string='Readonly', default=False)

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
        rules = super().create(prepared_vals_list)
        self.env.registry.clear_cache('default', 'templates')
        return rules

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
                super(ResProfileField, rule).write(values)
            self.env.registry.clear_cache('default', 'templates')
            return True
        result = super().write(vals)
        self.env.registry.clear_cache('default', 'templates')
        return result

    @api.onchange('profile_model_id')
    def _onchange_profile_model_id(self):
        if self.profile_model_id:
            self.profile_id = self.profile_model_id.profile_id
            self.model_id = self.profile_model_id.model_id

    @api.constrains('field_id', 'is_required', 'is_invisible', 'is_readonly')
    def _check_at_least_one_selected(self):
        """
        Validación para asegurar que al menos uno de los campos esté seleccionado.
        Si ninguno está seleccionado, arroja un error.
        """
        for record in self:
            if not (record.is_required or record.is_invisible or record.is_readonly):
                raise ValidationError(_("At least one option must be selected: 'Required', 'Invisible', or 'Readonly'."))

            if record.field_is_python_required and (
                record.is_invisible or record.is_readonly
            ):
                raise ValidationError(_(
                    "Fields required in Python can only use the Required option."
                ))

    @api.constrains('is_conditional', 'condition_domain', 'model_id')
    def _check_condition_domain(self):
        for rule in self.filtered('is_conditional'):
            try:
                domain = ast.literal_eval(rule.condition_domain or '[]')
            except (SyntaxError, ValueError) as error:
                raise ValidationError(_('The condition domain is invalid.')) from error
            if not isinstance(domain, list) or not domain:
                raise ValidationError(
                    _('Conditional rules require at least one condition.')
                )
            for field_name, operator, _value in rule._iter_domain_leaves(domain):
                model_fields = self.env[rule.model_id.model]._fields
                if '.' in field_name or field_name not in model_fields:
                    raise ValidationError(_(
                        "Condition field '%s' must be a direct field of the configured model.",
                        field_name,
                    ))
                if operator not in {
                    '=', '!=', '>', '>=', '<', '<=', 'in', 'not in',
                    'like', 'not like', 'ilike', 'not ilike', '=?',
                }:
                    raise ValidationError(_(
                        "Operator '%s' is not supported for dynamic view rules.",
                        operator,
                    ))

    def _iter_domain_leaves(self, domain):
        for token in domain:
            if isinstance(token, (list, tuple)) and len(token) == 3:
                yield token
            elif isinstance(token, list):
                yield from self._iter_domain_leaves(token)

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache('default', 'templates')
        return result
    
    @api.onchange('field_id')
    def _onchange_field_id(self):
        """ Ajusta los valores dependiendo de la selección de field_id """
        for field in self:
            field.is_required = False
            field.is_invisible = False
            field.is_readonly = False

    @api.constrains('profile_id', 'field_id')
    def _check_unique_field_in_profile(self):
        """ Impide que se repita el mismo campo dentro de un perfil """
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
                raise ValidationError(
                    _('The field rule does not match its model configuration.')
                )

    @api.onchange('is_required')
    def _onchange_is_required(self):
        """
        Asegura que, si 'is_required' está marcado, 'is_invisible' y 'is_readonly' se desmarquen.
        """
        if self.is_required:
            self.is_invisible = False
            self.is_readonly = False

    @api.onchange('is_invisible')
    def _onchange_is_invisible(self):
        """
        Asegura que, si 'is_invisible' está marcado, 'is_required' y 'is_readonly' se desmarquen.
        """
        if self.is_invisible:
            self.is_required = False
            self.is_readonly = False

    @api.onchange('is_readonly')
    def _onchange_is_readonly(self):
        """
        Asegura que, si 'is_readonly' está marcado, 'is_required' y 'is_invisible' se desmarquen.
        """
        if self.is_readonly:
            self.is_required = False
            self.is_invisible = False
