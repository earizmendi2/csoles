import random
import string
from collections import defaultdict
from odoo import api, models, fields, _
from odoo.exceptions import AccessError
from odoo.osv import expression


class AIAssistant(models.Model):
    _name = 'ai.assistant'
    _description = 'AI Assistant'
    _inherits = {'res.partner': 'partner_id'}
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    description = fields.Text(string="Description")
    config_id = fields.Many2one('ai.config', string="Configuration", required=True, groups='base.group_system')
    type = fields.Selection(related='config_id.type', string="Type")
    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict', auto_join=True, index=True)
    user_id = fields.Many2one('res.users', compute='_compute_user_id', precompute=True, store=True)
    context_id = fields.Many2one('ai.context', string="Assistant Context")
    is_superuser = fields.Boolean(string="Is Superuser", default=False,
                                  help="If True, the assistant will be able to access all data sources and models.")
    data_source_ids = fields.Many2many('ai.data.source', 'ai_assistant_data_source_rel', 'assistant_id', 'data_source_id',
                                       string="Data Sources")
    accessible_data_source_ids = fields.Many2many('ai.data.source', string="Accessible Data Sources",
                                                  compute='_compute_accessible_data_source_ids')
    has_vector_access = fields.Boolean(string="Has Vector Access", compute='_compute_has_vector_access')
    has_model_access = fields.Boolean(string="Has Model Access", compute='_compute_has_model_access')
    data_item_count = fields.Integer(string="Data Item Count", compute='_compute_data_item_count')
    group_ids = fields.Many2many('res.groups', string="Groups",
                                 help="Restrict the availability of this assistant to specific groups.")

    @api.depends('partner_id.user_ids')
    def _compute_user_id(self):
        for r in self:
            r.user_id = r.partner_id.with_context(active_test=False).user_ids[:1]

    @api.depends('is_superuser', 'data_source_ids')
    def _compute_accessible_data_source_ids(self):
        for r in self:
            r.accessible_data_source_ids = r.is_superuser and self.env['ai.data.source'].search([]) or r.data_source_ids

    @api.depends('accessible_data_source_ids')
    def _compute_data_item_count(self):
        items_per_source_count = dict(
            (res['id'], res['data_item_count'])
            for res in self.accessible_data_source_ids.read(['data_item_count'])
        )
        for r in self:
            r.data_item_count = sum(items_per_source_count.get(_id, 0) for _id in r.accessible_data_source_ids.ids)

    @api.depends('accessible_data_source_ids')
    def _compute_has_vector_access(self):
        for r in self:
            r.has_vector_access = bool(r.accessible_data_source_ids.filtered('data_item_count'))

    @api.depends('is_superuser', 'data_source_ids.type')
    def _compute_has_model_access(self):
        for r in self:
            r.has_model_access = r.is_superuser or bool(r.data_source_ids.filtered(lambda ds: ds.type == 'model'))

    def _create_user(self):
        self.ensure_one()
        user = self.env['res.users'].create({
            'login': '__%s__' % (''.join(random.choice(string.ascii_letters + string.digits) for i in range(10))),
            'partner_id': self.partner_id.id,
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        user.action_archive()
        return user

    @api.model_create_multi
    def create(self, vals_list):
        configs = super().create(vals_list)
        for config in configs.with_context(active_test=False):
            if not config.partner_id.user_ids:
                config._create_user()
        self.env.registry.clear_cache()
        return configs

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    def action_view_user(self):
        action = self.env['ir.actions.act_window']._for_xml_id('base.action_res_users')
        action['view_mode'] = 'form'
        action['views'] = [(self.env.ref('base.view_users_form').id, 'form')]
        action['res_id'] = self.user_id.id
        return action

    def action_view_data_items(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ai_base_gt.action_ai_data_item')
        action['domain'] = [('data_source_id.assistant_ids', 'in', self.ids)]
        return action

    def _get_accessible_data_sources_info(self):
        self.ensure_one()
        data_sources = self.accessible_data_source_ids.filtered('data_item_count')
        specs = []
        for source in data_sources:
            specs.append({
                'id': source.id,
                'name': source.name,
                'description': source.description,
                'type': source.type,
            })
        return specs

    def _get_accessible_models_info(self):
        self.ensure_one()
        if self.is_superuser:
            models = self.env['ir.model'].sudo().search([])
        else:
            models = self.data_source_ids.filtered(lambda ds: ds.type == 'model').sudo().model_id
        specs = []
        for model in models.with_context(lang='en_US'):
            if model.model not in self.env.registry:
                continue
            Model = self.env[model.model]
            if Model._auto and not Model._transient:
                specs.append({
                    'name': model.name,
                    'model': model.model,
                })
        return specs

    def _check_model_fields_access(self, model_name, requested_fields):
        """
        Check if the model and requested fields are allowed for this assistant.
        Returns the allowed fields list for the model if valid, otherwise raises AccessError.
        """
        self.ensure_one()
        if self.env.su or self.is_superuser:
            if requested_fields:
                return requested_fields
            else:
                return [
                    fname for fname, field in self.env[model_name]._fields.items()
                    if field.type != 'binary'
                ]
        allowed_models = defaultdict(set)
        for data_source in self.data_source_ids.filtered(lambda source: source.type == 'model'):
            allowed_models[data_source.model].update(data_source._get_access_fields())
        if model_name not in allowed_models:
            raise AccessError(_("Model %s is not allowed for this assistant.") % model_name)
        allowed_fields = allowed_models[model_name]
        if requested_fields:
            not_allowed = set(requested_fields) - allowed_fields
            if not_allowed:
                raise AccessError(_("Fields %s of model %s are not allowed for this assistant.") % (', '.join(not_allowed), model_name))
        return list(allowed_fields)

    def _get_model_domain_access(self, model_name):
        self.ensure_one()
        if self.env.su or self.is_superuser:
            return []
        data_sources = self.data_source_ids.filtered(
            lambda ds: ds.type == 'model' and ds.model == model_name
        )
        domain = expression.OR([ds._get_model_domain() for ds in data_sources])
        return domain
