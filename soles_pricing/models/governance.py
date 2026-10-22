"""Commercial governance. Published documents are immutable; revisions are explicit."""
import json
import uuid
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .configuration import require_config, invalidate_approvals
from .math import finite

PUBLICATION_TOKEN = object()
FX_TOKEN = object()


def internal(env):
    return env.context.get('_soles_publication') is PUBLICATION_TOKEN


def dump_value(record, name):
    field = record._fields[name]
    value = record[name]
    if field.type in ('many2one', 'many2many', 'one2many'):
        return value.ids if field.type != 'many2one' else value.id or False
    if field.type in ('date', 'datetime'):
        return str(value) if value else False
    return value


def audit(record, before, after, operation='write'):
    if before == after:
        return
    record.env['soles.pricing.audit'].sudo().create({
        'name': record.display_name, 'company_id': (record if record._name == 'res.company' else record.company_id if 'company_id' in record._fields and record.company_id else record.env.company).id,
        'model_name': record._name, 'record_id': record.id,
        'actor_id': record.env.uid, 'operation': operation,
        'changes': {'before': before, 'after': after},
    })


class Audit(models.Model):
    _name = 'soles.pricing.audit'
    _description = 'Bitácora inmutable de cambios comerciales'
    _order = 'id desc'
    name = fields.Char(string='Documento', required=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    model_name = fields.Char(string='Modelo', required=True, index=True)
    record_id = fields.Integer(string='ID de documento', required=True)
    actor_id = fields.Many2one('res.users', string='Usuario', required=True)
    operation = fields.Char(string='Operación', required=True)
    changes = fields.Json(string='Valores anteriores y nuevos', required=True)
    detail_text = fields.Text(string='Detalle', compute='_compute_text')

    def _compute_text(self):
        for r in self:
            r.detail_text = json.dumps(r.changes, ensure_ascii=False, indent=2, default=str)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('La bitácora se genera desde el servidor.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_('La bitácora es inmutable.'))

    def unlink(self):
        raise AccessError(_('La bitácora no se elimina.'))


class Version(models.Model):
    _name = 'soles.pricing.version'
    _description = 'Versión comercial publicada'
    _order = 'id desc'
    name = fields.Char(string='Documento', required=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    model_name = fields.Char(string='Modelo', required=True)
    record_id = fields.Integer(string='ID de documento', required=True)
    series_key = fields.Char(required=True, index=True)
    revision = fields.Integer(string='Revisión', required=True)
    publisher_id = fields.Many2one('res.users', string='Publicado por', required=True)
    published_at = fields.Datetime(string='Publicado el', default=fields.Datetime.now, required=True)
    justification = fields.Text(string='Justificación', required=True)
    payload = fields.Json(string='Condiciones publicadas', required=True)
    detail_text = fields.Text(string='Condiciones de la versión', compute='_compute_text')

    def _compute_text(self):
        for r in self:
            r.detail_text = json.dumps(r.payload, ensure_ascii=False, indent=2, default=str)
    _sql_constraints = [('series_revision', 'unique(model_name, series_key, revision)', 'La revisión ya fue publicada.')]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su or not internal(self.env):
            raise AccessError(_('Las versiones se generan al publicar.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_('Las versiones publicadas son inmutables.'))

    def unlink(self):
        raise AccessError(_('Las versiones publicadas no se eliminan.'))


class Published(models.AbstractModel):
    _name = 'soles.pricing.published'
    _description = 'Flujo de publicación comercial'
    state = fields.Selection([('draft', 'Borrador'), ('review', 'En revisión'), ('published', 'Publicada'), ('inactive', 'Inactiva')], default='draft', required=True, string='Estado', index=True, copy=False)
    series_key = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, required=True, copy=False, index=True)
    revision = fields.Integer(string='Revisión', readonly=True, copy=False)
    version_id = fields.Many2one('soles.pricing.version', string='Versión publicada', readonly=True, copy=False, ondelete='restrict')
    publisher_id = fields.Many2one('res.users', string='Publicado por', readonly=True, copy=False)
    published_at = fields.Datetime(string='Publicado el', readonly=True, copy=False)
    justification = fields.Text(string='Justificación comercial')

    def _document_payload(self):
        self.ensure_one()
        excluded = {'id', 'display_name', '__last_update', 'create_uid', 'create_date', 'write_uid', 'write_date', 'state', 'version_id', 'publisher_id', 'published_at', 'revision'}
        return {name: dump_value(self, name) for name, f in self._fields.items()
                if name not in excluded and f.store and not name.startswith(('message_', 'activity_')) and f.type not in ('binary', 'one2many') and not f.related and not f.compute}

    @api.model_create_multi
    def create(self, vals_list):
        values = []
        for v in vals_list:
            v = dict(v)
            if v.get('state', 'draft') != 'draft' or any(v.get(k) for k in ('version_id', 'revision', 'publisher_id', 'published_at')):
                raise AccessError(_('Cree un borrador y utilice el flujo de publicación.'))
            if not internal(self.env):
                v['series_key'] = str(uuid.uuid4())
            values.append(v)
        records = super().create(values)
        for rec in records:
            audit(rec, {}, rec._document_payload(), 'create')
        return records

    def write(self, vals):
        metadata = {'state', 'series_key', 'revision', 'version_id', 'publisher_id', 'published_at'}
        if not internal(self.env):
            if metadata.intersection(vals):
                raise AccessError(_('Use los botones de revisión y publicación.'))
            fields_changed = set(vals) - {'message_main_attachment_id', 'message_follower_ids', 'activity_ids'}
            if fields_changed and self.filtered(lambda r: r.state in ('published', 'inactive')):
                raise UserError(_('El documento publicado es inmutable. Cree una nueva revisión.'))
        snapshots = {rec.id: rec._document_payload() for rec in self}
        states_before = {rec.id: {k: dump_value(rec, k) for k in metadata if k in vals} for rec in self}
        result = super().write(vals)
        for rec in self:
            audit(rec, snapshots[rec.id], rec._document_payload(), 'write')
        if metadata.intersection(vals):
            for rec in self:
                audit(rec, states_before[rec.id], {k: dump_value(rec, k) for k in metadata if k in vals}, 'workflow')
        return result

    def unlink(self):
        if self.filtered(lambda r: r.state != 'draft' or r.revision):
            raise AccessError(_('Conserve el historial; desactive documentos publicados.'))
        for rec in self:
            audit(rec, rec._document_payload(), {}, 'unlink')
        return super().unlink()

    def _transition(self, vals):
        return self.sudo().with_context(_soles_publication=PUBLICATION_TOKEN).write(vals)

    def action_submit(self):
        self.check_access('write')
        if self.filtered(lambda r: r.state != 'draft' or not r.justification):
            raise UserError(_('Indique la justificación y envíe un borrador a revisión.'))
        self._transition({'state': 'review'})
        return True

    def action_return_draft(self):
        self.check_access('write')
        if self.filtered(lambda r: r.state != 'review'):
            raise UserError(_('Solo se pueden regresar documentos en revisión.'))
        self._transition({'state': 'draft'})
        return True

    def _validate_publication(self):
        return True

    def action_publish(self):
        self.check_access('read')
        if not self.env.su and not self.env.user.has_group('soles_pricing.group_publisher'):
            raise AccessError(_('Necesita la facultad de publicar políticas comerciales.'))
        for rec in self:
            if rec.company_id not in self.env.companies:
                raise AccessError(_('Compañía no permitida.'))
            if rec.state != 'review' or not rec.justification:
                raise UserError(_('Publique un documento revisado con justificación.'))
            # A real update on the root row also forces serialization failure for
            # concurrent publishers with an older repeatable-read snapshot.
            root = self.sudo().with_context(active_test=False).search([('series_key', '=', rec.series_key)], order='id', limit=1)
            self.env.cr.execute('UPDATE ' + self._table + ' SET write_date=write_date WHERE id=%s', [root.id])
            rec._validate_publication()
            previous = self.sudo().with_context(active_test=False).search([('series_key', '=', rec.series_key), ('state', '=', 'published'), ('id', '!=', rec.id)])
            previous._transition({'state': 'inactive'})
            revisions = self.env['soles.pricing.version'].sudo().search([('model_name', '=', rec._name), ('series_key', '=', rec.series_key)], order='revision desc', limit=1)
            revision = (revisions.revision or 0) + 1
            version = self.env['soles.pricing.version'].sudo().with_context(_soles_publication=PUBLICATION_TOKEN).create({
                'name': rec.name, 'company_id': rec.company_id.id, 'model_name': rec._name,
                'record_id': rec.id, 'series_key': rec.series_key, 'revision': revision,
                'publisher_id': self.env.uid, 'justification': rec.justification, 'payload': rec._document_payload(),
            })
            rec._transition({'state': 'published', 'active': True, 'revision': revision,
                             'version_id': version.id, 'publisher_id': self.env.uid, 'published_at': fields.Datetime.now()})
            invalidate_approvals(self.env, rec.company_id)
        return True

    def action_deactivate(self):
        self.check_access('read')
        if not self.env.su and not self.env.user.has_group('soles_pricing.group_publisher'):
            raise AccessError(_('Solo un publicador puede retirar una política publicada.'))
        self._transition({'state': 'inactive'})
        invalidate_approvals(self.env, self.company_id)
        return True

    def action_new_revision(self):
        self.ensure_one()
        self.check_access('write')
        if self.state not in ('published', 'inactive'):
            raise UserError(_('La nueva revisión se crea desde un documento publicado.'))
        rec = self.with_context(_soles_publication=PUBLICATION_TOKEN).copy({'state': 'draft', 'active': True,
            'series_key': self.series_key, 'revision': 0, 'version_id': False, 'publisher_id': False, 'published_at': False,
            'justification': False})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': rec.id, 'view_mode': 'form', 'target': 'current'}


class Family(models.Model):
    _name = 'soles.pricing.family'
    _inherit = ['mail.thread']
    _description = 'Familia comercial independiente'
    _parent_store = True
    _check_company_auto = True
    name = fields.Char(string='Familia', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    parent_id = fields.Many2one('soles.pricing.family', string='Familia superior', check_company=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    method = fields.Selection([('native', 'Lista nativa'), ('list', 'Precio de referencia'), ('cost_margin', 'Costo / (1 − margen)')], default='native', required=True, string='Método predeterminado')
    target_margin = fields.Float(string='Margen objetivo (%)')
    min_margin = fields.Float(string='Margen mínimo operativo (%)')
    exception_margin = fields.Float(string='Margen excepcional absoluto (%)')
    benefit_policy = fields.Selection([('inherit', 'Heredar política de compañía'), ('allow', 'Permitir beneficio adicional'), ('deny', 'Sin acumulación de beneficio')], required=True, default='inherit', string='Beneficios acumulables')

    @api.constrains('target_margin', 'min_margin', 'exception_margin', 'parent_id')
    def _check_values(self):
        for r in self:
            if not finite(r.target_margin, r.min_margin, r.exception_margin) or not 0 <= r.exception_margin <= r.min_margin < 100 or not 0 <= r.target_margin < 100:
                raise ValidationError(_('Revise márgenes: excepcional ≤ operativo; porcentajes entre 0 y menos de 100.'))
            if r.parent_id and r.parent_id.company_id != r.company_id:
                raise ValidationError(_('La familia superior debe ser de la misma compañía.'))
            if r._has_cycle():
                raise ValidationError(_('No se admiten ciclos en familias.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for r, values in zip(records, vals_list):
            audit(r, {}, {k: dump_value(r, k) for k in values}, 'create')
        return records

    def write(self, vals):
        require_config(self.env)
        before = {r.id: {k: dump_value(r, k) for k in vals} for r in self}
        result = super().write(vals)
        for r in self:
            audit(r, before[r.id], {k: dump_value(r, k) for k in vals})
        invalidate_approvals(self.env, self.company_id)
        return result


class ProductPolicy(models.Model):
    _name = 'soles.pricing.product.policy'
    _description = 'Clasificación y tratamiento comercial de productos'
    name = fields.Char(string='Clasificación', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    allow_sale = fields.Boolean(string='Permitir venta interna', default=False)
    allow_b2b = fields.Boolean(string='Disponible para futuro B2B', default=False)
    require_approval = fields.Boolean(string='Requerir autorización por operación', default=False)
    allow_missing_reference = fields.Boolean(string='Permitir cotización especial sin referencia', default=False)
    minimum_reference = fields.Monetary(string='Referencia mínima aceptada', currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.constrains('minimum_reference')
    def _check_reference(self):
        for r in self:
            if not finite(r.minimum_reference) or r.minimum_reference < 0:
                raise ValidationError(_('Referencia mínima inválida.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for r, values in zip(records, vals_list):
            audit(r, {}, {k: dump_value(r, k) for k in values}, 'create')
        return records

    def write(self, vals):
        require_config(self.env)
        before = {r.id: {k: dump_value(r, k) for k in vals} for r in self}
        result = super().write(vals)
        for r in self:
            audit(r, before[r.id], {k: dump_value(r, k) for k in vals})
        invalidate_approvals(self.env, self.company_id)
        return result


class PublishedRule(models.Model):
    _name = 'soles.pricing.rule'
    _inherit = ['soles.pricing.rule', 'soles.pricing.published']
    agreement_reference = fields.Char(string='Acuerdo / contrato')

    def _validate_publication(self):
        return super()._validate_publication()


class PublishedCost(models.Model):
    _name = 'soles.pricing.cost'
    _inherit = ['soles.pricing.cost', 'soles.pricing.published']
    source = fields.Selection([('manual', 'Cotización / documento comercial'), ('purchase', 'Compra histórica'), ('replacement', 'Reposición'), ('avco_snapshot', 'Captura del costo contable'), ('import', 'Importación revisada')], default='manual', required=True, string='Fuente')
    source_reference = fields.Char(string='Documento / referencia de origen')
    captured_at = fields.Datetime(string='Capturado el', default=fields.Datetime.now, required=True)

    def _validate_publication(self):
        for r in self:
            if not r.source_reference:
                raise ValidationError(_('Indique la fuente documental del costo.'))
        return super()._validate_publication()

    def action_capture_standard(self):
        self.check_access('write')
        for r in self:
            r.write({'amount': r.product_id.with_company(r.company_id).standard_price,
                     'currency_id': r.company_id.currency_id.id, 'source': 'avco_snapshot',
                     'source_reference': _('Captura explícita del costo contable'), 'captured_at': fields.Datetime.now()})
        return True


class Fx(models.Model):
    _name = 'soles.pricing.fx'
    _inherit = ['soles.pricing.published', 'mail.thread']
    _description = 'Tipo de cambio comercial publicado'
    name = fields.Char(required=True, string='Referencia')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda origen', required=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de compañía')
    rate = fields.Float(required=True, digits=(16, 8), string='Unidades de moneda de compañía por 1 origen')
    date_start = fields.Date(required=True, default=fields.Date.today)
    date_end = fields.Date()
    source_reference = fields.Char(string='Fuente comercial', required=True)

    @api.constrains('rate', 'currency_id', 'date_start', 'date_end', 'state')
    def _check_rate(self):
        for r in self:
            if not finite(r.rate) or r.rate <= 0 or r.currency_id == r.company_id.currency_id or (r.date_end and r.date_start > r.date_end):
                raise ValidationError(_('Tipo de cambio, moneda o vigencia inválidos.'))
            if r.state == 'published':
                self.env.cr.execute('UPDATE res_company SET write_date=write_date WHERE id=%s', [r.company_id.id])
                if self.search_count([('id', '!=', r.id), ('company_id', '=', r.company_id.id), ('currency_id', '=', r.currency_id.id), ('state', '=', 'published'), ('active', '=', True), ('date_start', '<=', r.date_end or '9999-12-31'), '|', ('date_end', '=', False), ('date_end', '>=', r.date_start)]):
                    raise ValidationError(_('Hay tipos de cambio comerciales superpuestos.'))


class Currency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company=None, date=None):
        company = company or self.env.company
        if self.env.context.get('_soles_fx') is FX_TOKEN and company.soles_fx_mode == 'commercial':
            return self.env['soles.pricing.engine']._fx_convert(1, from_currency, to_currency, company, fields.Date.to_date(date or fields.Date.today()))[0]
        return super()._get_conversion_rate(from_currency, to_currency, company, date)


class Limit(models.Model):
    _name = 'soles.pricing.limit'
    _inherit = ['soles.pricing.scope', 'soles.pricing.published', 'mail.thread']
    _description = 'Restricción comercial / precio mínimo de fabricante'
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    minimum_price = fields.Monetary(string='Precio neto mínimo por UdM base', required=True)
    overridable = fields.Boolean(string='Admite excepción expresa', default=False)

    @api.constrains('minimum_price')
    def _check_minimum(self):
        for r in self:
            if not finite(r.minimum_price) or r.minimum_price < 0:
                raise ValidationError(_('Precio mínimo inválido.'))


class Precedence(models.Model):
    _name = 'soles.pricing.precedence'
    _description = 'Matriz configurable de precedencias'
    _order = 'sequence, id'
    name = fields.Char(required=True, string='Criterio')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    operation = fields.Selection([('rule', 'Reglas de precios'), ('authority', 'Facultades')], required=True, default='rule')
    sequence = fields.Integer(default=10, string='Orden')
    scope = fields.Selection([('any', 'Cualquier alcance'), ('partner', 'Cliente'), ('segment', 'Segmento'), ('general', 'General')], default='any', required=True)
    target = fields.Selection([('any', 'Cualquier criterio'), ('sku', 'SKU'), ('family_brand', 'Familia y marca'), ('brand', 'Marca'), ('family', 'Familia comercial'), ('category', 'Categoría heredada'), ('general', 'Sin criterio de producto')], default='any', required=True)
    subject = fields.Selection([('any', 'Cualquiera'), ('user', 'Usuario específico'), ('group', 'Rol')], default='any', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for r, values in zip(records, vals_list):
            audit(r, {}, {k: dump_value(r, k) for k in values}, 'create')
        return records

    def write(self, vals):
        require_config(self.env)
        before = {r.id: {k: dump_value(r, k) for k in vals} for r in self}
        result = super().write(vals)
        for r in self:
            audit(r, before[r.id], {k: dump_value(r, k) for k in vals})
        invalidate_approvals(self.env, self.company_id)
        return result


class Route(models.Model):
    _name = 'soles.pricing.route'
    _inherit = ['soles.pricing.scope', 'mail.thread']
    _description = 'Matriz de responsables y escalamiento'
    _order = 'sequence, id'
    reviewer_ids = fields.Many2many('res.users', string='Responsables')
    reviewer_group_id = fields.Many2one('res.groups', string='Grupo de responsables')
    min_discount_amount = fields.Monetary(string='Descuento monetario mínimo de la oferta', currency_field='currency_id')
    max_discount_amount = fields.Monetary(string='Máximo (0 = sin límite)', currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.constrains('reviewer_ids', 'reviewer_group_id', 'min_discount_amount', 'max_discount_amount')
    def _check_route(self):
        for r in self:
            if not r.reviewer_ids and not r.reviewer_group_id:
                raise ValidationError(_('Indique responsables o grupo.'))
            if not finite(r.min_discount_amount, r.max_discount_amount) or r.min_discount_amount < 0 or (r.max_discount_amount and r.max_discount_amount < r.min_discount_amount):
                raise ValidationError(_('Rango monetario de enrutamiento inválido.'))
