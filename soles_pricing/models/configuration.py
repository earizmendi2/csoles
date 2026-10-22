from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .math import finite


CONFIG_GROUP = 'soles_pricing.group_config'


def require_config(env):
    if not env.su and not env.user.has_group(CONFIG_GROUP):
        raise AccessError(env._('Solo el administrador de precios puede cambiar esta configuración.'))


def invalidate_approvals(env, companies=None):
    domain = [('state', 'in', ['pending', 'approved'])]
    if companies:
        domain.append(('company_id', 'in', companies.ids))
    env['soles.pricing.approval'].sudo().search(domain).write({'state': 'invalid'})


def audit_before(records, vals):
    from .governance import dump_value
    return {r.id: {k: dump_value(r, k) for k in vals if k in r._fields} for r in records}


def audit_after(records, vals, before, operation='write'):
    from .governance import audit, dump_value
    for r in records:
        audit(r, before.get(r.id, {}), {k: dump_value(r, k) for k in vals if k in r._fields}, operation)


def protect_native(env, vals, keys):
    companies = env['res.company'].sudo().search([('soles_pricing_mode', '!=', 'off')])
    source_fields = set(companies.mapped('soles_brand_field_id.name'))
    if (keys | source_fields).intersection(vals) and companies:
        require_config(env)
        invalidate_approvals(env)


class Company(models.Model):
    _inherit = 'res.company'

    soles_pricing_mode = fields.Selection([
        ('off', 'Nativo'), ('audit', 'Comparación'), ('enforce', 'Control activo')],
        default='off', required=True, string='Modo de precios Soles')
    soles_discount_mode = fields.Selection([
        ('additive', 'Sumados sobre la base'), ('sequential', 'Sucesivos')],
        default='sequential', required=True, string='Modalidad heredada (vendedor siempre sucesivo)')
    soles_allow_benefit = fields.Boolean(string='Permitir beneficio adicional a la regla base', default=False)
    soles_fx_mode = fields.Selection([('commercial', 'Tipo de cambio comercial publicado'), ('native', 'Tipo de cambio contable nativo')], default='commercial', required=True, string='Política cambiaria')
    soles_revalidate_cost = fields.Boolean(string='Reevaluar costo publicado al confirmar', default=True)
    soles_brand_field_id = fields.Many2one('ir.model.fields', string='Campo de marca existente (opcional)', domain="[('model', 'in', ['product.template', 'product.product']), ('ttype', '=', 'many2one')]")
    soles_min_margin = fields.Float(string='Piso de margen sobre venta (%)', default=0)
    soles_require_cost = fields.Boolean(string='Exigir costo comercial positivo', default=True)
    soles_allow_self_approval = fields.Boolean(string='Permitir autoaprobación', default=False)
    soles_approval_hours = fields.Float(string='Vigencia de aprobación (horas)', default=24)
    soles_notify_reviewers = fields.Boolean(string='Crear actividades para aprobadores elegibles', default=True)

    @api.constrains('soles_min_margin', 'soles_approval_hours')
    def _check_soles_config(self):
        for rec in self:
            if not finite(rec.soles_min_margin, rec.soles_approval_hours) or not 0 <= rec.soles_min_margin < 100 or rec.soles_approval_hours <= 0:
                raise ValidationError(_('Piso entre 0 y menos de 100; vigencia positiva.'))

    def write(self, vals):
        policy = {k: v for k, v in vals.items() if k.startswith('soles_')}
        before = audit_before(self, policy) if policy else {}
        if policy:
            require_config(self.env)
            invalidate_approvals(self.env, self)
        result = super().write(vals)
        if policy:
            audit_after(self, policy, before)
        return result


class Settings(models.TransientModel):
    _inherit = 'res.config.settings'

    soles_pricing_mode = fields.Selection(related='company_id.soles_pricing_mode', readonly=False)
    soles_discount_mode = fields.Selection(related='company_id.soles_discount_mode', readonly=False)
    soles_min_margin = fields.Float(related='company_id.soles_min_margin', readonly=False)
    soles_require_cost = fields.Boolean(related='company_id.soles_require_cost', readonly=False)
    soles_allow_self_approval = fields.Boolean(related='company_id.soles_allow_self_approval', readonly=False)
    soles_approval_hours = fields.Float(related='company_id.soles_approval_hours', readonly=False)


class Segment(models.Model):
    _name = 'soles.pricing.segment'
    _description = 'Segmento comercial editable'
    _check_company_auto = True
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)
    sequence = fields.Integer(string='Orden', default=10)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    _sql_constraints = [('name_company', 'unique(name, company_id)', 'Segmento duplicado en la compañía.')]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for r, values in zip(records, vals_list):
            audit_after(r, values, {}, 'create')
        return records

    def write(self, vals):
        before = audit_before(self, vals)
        invalidate_approvals(self.env, self.company_id)
        result = super().write(vals)
        audit_after(self, vals, before)
        return result


class Brand(models.Model):
    _name = 'soles.pricing.brand'
    _description = 'Marca comercial'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)
    native_model = fields.Char(string='Modelo de marca existente')
    native_id = fields.Integer(string='ID de marca existente')
    _sql_constraints = [('name_unique', 'unique(name)', 'Marca duplicada.')]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for r, values in zip(records, vals_list):
            audit_after(r, values, {}, 'create')
        return records

    def write(self, vals):
        before = audit_before(self, vals)
        invalidate_approvals(self.env)
        result = super().write(vals)
        audit_after(self, vals, before)
        return result


class Partner(models.Model):
    _inherit = 'res.partner'

    soles_segment_id = fields.Many2one('soles.pricing.segment', string='Nivel del cliente', company_dependent=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any('soles_segment_id' in v for v in vals_list):
            require_config(self.env)
        return super().create(vals_list)

    def write(self, vals):
        policy = {'soles_segment_id': vals['soles_segment_id']} if 'soles_segment_id' in vals else {}
        before = audit_before(self, policy) if policy else {}
        if policy:
            require_config(self.env)
            invalidate_approvals(self.env)
        result = super().write(vals)
        if policy:
            audit_after(self, policy, before)
        return result

    @api.constrains('soles_segment_id')
    def _check_segment(self):
        for rec in self:
            if rec.soles_segment_id and rec.soles_segment_id.company_id != self.env.company:
                raise ValidationError(_('El segmento debe pertenecer a la compañía activa.'))


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    soles_brand_id = fields.Many2one('soles.pricing.brand', string='Marca Soles')
    soles_family_id = fields.Many2one('soles.pricing.family', string='Familia comercial Soles', company_dependent=True)
    soles_product_policy_id = fields.Many2one('soles.pricing.product.policy', string='Clasificación comercial', company_dependent=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({'soles_brand_id', 'soles_family_id', 'soles_product_policy_id'}) for v in vals_list):
            require_config(self.env)
        return super().create(vals_list)

    def write(self, vals):
        keys = {'list_price', 'categ_id', 'uom_id', 'company_id', 'soles_brand_id', 'soles_family_id', 'soles_product_policy_id', 'taxes_id', 'attribute_line_ids'}
        protect_native(self.env, vals, keys)
        policy = {k: v for k, v in vals.items() if k in keys}
        before = audit_before(self, policy) if policy else {}
        if set(vals).intersection({'soles_brand_id', 'soles_family_id', 'soles_product_policy_id'}):
            require_config(self.env)
        result = super().write(vals)
        if policy:
            audit_after(self, policy, before)
        return result

    @api.constrains('soles_family_id', 'soles_product_policy_id')
    def _check_commercial_company(self):
        for r in self:
            for record in (r.soles_family_id, r.soles_product_policy_id):
                if record and record.company_id != self.env.company:
                    raise ValidationError(_('Clasificación/familia de otra compañía.'))


class ProductVariant(models.Model):
    _inherit = 'product.product'

    def _soles_commercial_brand(self, company):
        self.ensure_one()
        product = self.sudo().with_company(company)
        if product.soles_brand_id:
            return product.soles_brand_id
        field = company.sudo().soles_brand_field_id
        if not field or field.ttype != 'many2one' or field.model not in ('product.product', 'product.template'):
            return self.env['soles.pricing.brand']
        target = product if field.model == 'product.product' else product.product_tmpl_id
        native = target[field.name]
        return self.env['soles.pricing.brand'].sudo().search([('native_model', '=', native._name), ('native_id', '=', native.id)], limit=1) if native else self.env['soles.pricing.brand']

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({'soles_brand_id', 'soles_family_id', 'soles_product_policy_id'}) for v in vals_list):
            require_config(self.env)
        return super().create(vals_list)

    def write(self, vals):
        protect_native(self.env, vals, {'list_price', 'lst_price', 'categ_id', 'uom_id', 'company_id', 'soles_brand_id', 'soles_family_id', 'soles_product_policy_id', 'price_extra', 'product_template_attribute_value_ids', 'taxes_id'})
        return super().write(vals)


class Category(models.Model):
    _inherit = 'product.category'

    def write(self, vals):
        protect_native(self.env, vals, {'parent_id'})
        return super().write(vals)


class Pricelist(models.Model):
    _inherit = 'product.pricelist'

    @api.model_create_multi
    def create(self, vals_list):
        protect_native(self.env, {'pricelist': True}, {'pricelist'})
        return super().create(vals_list)

    def write(self, vals):
        protect_native(self.env, vals, set(vals))
        return super().write(vals)


class PricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    @api.model_create_multi
    def create(self, vals_list):
        protect_native(self.env, {'items': True}, {'items'})
        return super().create(vals_list)

    def write(self, vals):
        protect_native(self.env, vals, set(vals))
        return super().write(vals)

    def unlink(self):
        protect_native(self.env, {'items': True}, {'items'})
        return super().unlink()


class Scope(models.AbstractModel):
    _name = 'soles.pricing.scope'
    _description = 'Criterios comunes de precios'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)
    sequence = fields.Integer(default=10, string='Prioridad (menor gana)')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company, index=True)
    scope = fields.Selection([('general', 'General'), ('segment', 'Nivel de cliente'), ('partner', 'Cliente')], string='Alcance', required=True, default='general')
    segment_id = fields.Many2one('soles.pricing.segment', string='Nivel del cliente', check_company=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', string='Cliente', check_company=True, ondelete='restrict')
    category_id = fields.Many2one('product.category', string='Categoría nativa (compatibilidad)')
    family_id = fields.Many2one('soles.pricing.family', string='Familia comercial', check_company=True, ondelete='restrict')
    quote_currency_id = fields.Many2one('res.currency', string='Solo cotizaciones en moneda')
    brand_id = fields.Many2one('soles.pricing.brand', string='Marca', ondelete='restrict')
    product_ids = fields.Many2many('product.product', string='SKU / variantes', check_company=True)
    min_qty = fields.Float(default=0, string='Cantidad mínima en UdM del producto')
    max_qty = fields.Float(default=0, string='Máxima (0 = sin límite)')
    date_start = fields.Date(string='Desde')
    date_end = fields.Date(string='Hasta (inclusive)')
    notes = fields.Text(string='Notas')

    @api.onchange('scope')
    def _onchange_scope(self):
        for rec in self:
            if rec.scope != 'partner':
                rec.partner_id = False
            if rec.scope != 'segment':
                rec.segment_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if 'state' not in records._fields:
            invalidate_approvals(self.env, records.company_id)
            for r, values in zip(records, vals_list):
                audit_after(r, values, {}, 'create')
        return records

    def write(self, vals):
        mutable = 'state' not in self._fields
        before = audit_before(self, vals) if mutable else {}
        if mutable:
            invalidate_approvals(self.env, self.company_id)
        result = super().write(vals)
        if mutable:
            audit_after(self, vals, before)
        return result

    def unlink(self):
        if 'state' not in self._fields:
            from .governance import audit
            for r in self:
                audit(r, audit_before(r, [n for n, f in r._fields.items() if f.store and not f.compute and not n.startswith(('message_', 'activity_')) and f.type != 'binary'])[r.id], {}, 'unlink')
            invalidate_approvals(self.env, self.company_id)
        return super().unlink()

    @api.constrains('scope', 'segment_id', 'partner_id', 'min_qty', 'max_qty', 'date_start', 'date_end')
    def _check_scope(self):
        for rec in self:
            if (rec.scope == 'segment') != bool(rec.segment_id) or (rec.scope == 'partner') != bool(rec.partner_id):
                raise ValidationError(_('Seleccione únicamente el segmento o cliente correspondiente al alcance.'))
            if not finite(rec.min_qty, rec.max_qty) or rec.min_qty < 0 or rec.max_qty < 0 or (rec.max_qty and rec.max_qty < rec.min_qty):
                raise ValidationError(_('Rango de volumen inválido.'))
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_('Vigencia inválida.'))

    def _matches(self, partner, product, qty, date):
        self.ensure_one()
        segment = partner.with_company(self.company_id).commercial_partner_id.soles_segment_id
        return (
            (self.scope != 'partner' or self.partner_id.commercial_partner_id == partner.commercial_partner_id)
            and (self.scope != 'segment' or (self.segment_id.active and self.segment_id == segment))
            and (not self.product_ids or product in self.product_ids)
            and (not self.brand_id or self.brand_id == product._soles_commercial_brand(self.company_id))
            and (not self.category_id or self.category_id.id in [int(x) for x in product.categ_id.parent_path.split('/') if x])
            and (not self.family_id or (product.with_company(self.company_id).soles_family_id and self.family_id.id in [int(x) for x in product.with_company(self.company_id).soles_family_id.parent_path.split('/') if x]))
            and qty >= self.min_qty and (not self.max_qty or qty <= self.max_qty)
            and (not self.date_start or date >= self.date_start)
            and (not self.date_end or date <= self.date_end)
        )

    def _rank(self):
        self.ensure_one()
        target = 'sku' if self.product_ids else 'family_brand' if self.family_id and self.brand_id else 'brand' if self.brand_id else 'family' if self.family_id else 'category' if self.category_id else 'general'
        operation = 'authority' if self._name == 'soles.pricing.authority' else 'rule'
        subject = ('user' if self.user_id else 'group') if operation == 'authority' else 'any'
        priorities = self.env['soles.pricing.precedence'].sudo().search([('company_id', '=', self.company_id.id), ('active', '=', True), ('operation', '=', operation)], order='sequence, id')
        match = priorities.filtered(lambda r: r.scope in ('any', self.scope) and r.target in ('any', target) and r.subject in ('any', subject))[:1]
        return (self.sequence, match.sequence if match else float('inf'), -self.min_qty, self.id)


class Rule(models.Model):
    _name = 'soles.pricing.rule'
    _inherit = ['soles.pricing.scope', 'mail.thread']
    _description = 'Regla de precio o beneficio'
    _order = 'sequence, id'

    stage = fields.Selection(string='Etapa', selection=[('base', 'Precio base'), ('benefit', 'Beneficio adicional')], required=True, default='base', tracking=True)
    method = fields.Selection(string='Método de precio', selection=[('native', 'Lista de precios nativa'), ('list', 'Precio de venta del producto'), ('fixed', 'Precio fijo'), ('cost_margin', 'Costo / (1 − margen)'), ('cost_markup', 'Costo × (1 + recargo)')], required=True, default='native', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id)
    fixed_price = fields.Monetary(string='Precio fijo sin impuestos', currency_field='currency_id')
    rate = fields.Float(string='Margen / recargo (%)')
    discount_pct = fields.Float(string='Descuento (%)', tracking=True)
    min_margin = fields.Float(string='Piso de margen (%)', tracking=True)

    @api.constrains('rate', 'discount_pct', 'fixed_price', 'min_margin', 'method')
    def _check_values(self):
        for r in self:
            if not finite(r.rate, r.discount_pct, r.fixed_price, r.min_margin) or r.rate < 0 or r.fixed_price < 0 or not 0 <= r.discount_pct <= 100 or not 0 <= r.min_margin < 100 or (r.method == 'cost_margin' and r.rate >= 100):
                raise ValidationError(_('Precio, descuento, margen o recargo inválido.'))

    def action_preview_products(self):
        self.ensure_one()
        self.check_access('read')
        domain = [('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)]
        if self.category_id:
            domain.append(('categ_id', 'child_of', self.category_id.id))
        if self.family_id:
            domain.append(('soles_family_id', 'child_of', self.family_id.id))
        if self.brand_id:
            products = self.env['product.product'].with_company(self.company_id).search(domain)
            domain.append(('id', 'in', products.filtered(lambda p: p._soles_commercial_brand(self.company_id) == self.brand_id).ids))
        if self.product_ids:
            domain.append(('id', 'in', self.product_ids.ids))
        return {'type': 'ir.actions.act_window', 'name': _('Productos alcanzados (sin validar volumen ni vigencia)'),
                'res_model': 'product.product', 'view_mode': 'list,form', 'domain': domain}


class Authority(models.Model):
    _name = 'soles.pricing.authority'
    _inherit = ['soles.pricing.scope', 'mail.thread']
    _description = 'Facultad de descuento o aprobación'
    _order = 'sequence, id'

    operation = fields.Selection(string='Operación', selection=[('discount', 'Descontar'), ('approve', 'Aprobar')], required=True, default='discount', tracking=True)
    user_id = fields.Many2one('res.users', string='Usuario específico')
    group_id = fields.Many2one('res.groups', string='Rol / grupo')
    max_discount = fields.Float(string='Descuento adicional máximo (%)', tracking=True)
    min_margin = fields.Float(string='Margen mínimo permitido (%)', tracking=True)
    override_floor = fields.Boolean(string='Puede autorizar por debajo del piso comercial', tracking=True)
    override_manufacturer = fields.Boolean(string='Puede exceptuar restricciones que lo permitan', tracking=True)
    allow_manual_quote = fields.Boolean(string='Puede aprobar productos de cotización especial', tracking=True)
    limit_discount_amount = fields.Boolean(string='Limitar descuento monetario de la oferta', tracking=True)
    max_discount_amount = fields.Monetary(string='Descuento máximo por oferta', currency_field='currency_id', tracking=True)
    limit_order_amount = fields.Boolean(string='Limitar importe neto de la oferta', tracking=True)
    max_order_amount = fields.Monetary(string='Importe neto máximo por oferta', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.constrains('user_id', 'group_id', 'max_discount', 'min_margin', 'operation', 'override_floor', 'max_discount_amount', 'max_order_amount')
    def _check_authority(self):
        for r in self:
            if bool(r.user_id) == bool(r.group_id):
                raise ValidationError(_('Seleccione un usuario o un rol, exclusivamente.'))
            if not finite(r.max_discount, r.min_margin) or not 0 <= r.max_discount <= 100 or not 0 <= r.min_margin < 100:
                raise ValidationError(_('Porcentajes fuera de rango.'))
            if r.override_floor and r.operation != 'approve':
                raise ValidationError(_('Solo una facultad de aprobación puede exceptuar el piso.'))
            if not finite(r.max_discount_amount, r.max_order_amount) or min(r.max_discount_amount, r.max_order_amount) < 0:
                raise ValidationError(_('Límites monetarios inválidos.'))


class Cost(models.Model):
    _name = 'soles.pricing.cost'
    _inherit = ['mail.thread']
    _description = 'Costo comercial independiente del costo contable'
    _check_company_auto = True
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    product_id = fields.Many2one('product.product', string='Producto', required=True, check_company=True, ondelete='restrict')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(required=True, tracking=True, string='Costo base por UdM del producto')
    freight = fields.Monetary(tracking=True, string='Flete')
    other = fields.Monetary(tracking=True, string='Otros costos')
    date_start = fields.Date(string='Desde', required=True, default=fields.Date.today)
    date_end = fields.Date(string='Hasta')
    notes = fields.Text(string='Notas')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if 'state' not in records._fields:
            invalidate_approvals(self.env, records.company_id)
        return records

    def write(self, vals):
        if 'state' not in self._fields:
            invalidate_approvals(self.env, self.company_id)
        return super().write(vals)

    def unlink(self):
        if 'state' not in self._fields:
            invalidate_approvals(self.env, self.company_id)
        return super().unlink()

    @api.constrains('amount', 'freight', 'other', 'date_start', 'date_end', 'product_id', 'active', 'state')
    def _check_cost(self):
        for r in self:
            if not finite(r.amount, r.freight, r.other) or min(r.amount, r.freight, r.other) < 0 or (r.date_end and r.date_start > r.date_end):
                raise ValidationError(_('Costo o vigencia inválidos.'))
            # Serialize concurrent inserts for one product; avoid ambiguous overlapping costs.
            self.env.cr.execute('UPDATE product_product SET write_date=write_date WHERE id=%s', [r.product_id.id])
            if r.state == 'published' and r.active and self.search_count([('id', '!=', r.id), ('state', '=', 'published'), ('active', '=', True), ('company_id', '=', r.company_id.id), ('product_id', '=', r.product_id.id), '|', ('date_end', '=', False), ('date_end', '>=', r.date_start), ('date_start', '<=', r.date_end or '9999-12-31')]):
                raise ValidationError(_('Hay otro costo comercial con vigencia superpuesta.'))

