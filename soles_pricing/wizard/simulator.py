from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError
from odoo.addons.soles_pricing.models.configuration import require_config
from odoo.addons.soles_pricing.models.sale import _NATIVE_DOWNPAYMENT


class Simulator(models.TransientModel):
    _name = 'soles.pricing.simulator'
    _description = 'Simulador comercial sin modificar cotizaciones'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, check_company=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True, check_company=True)
    quantity = fields.Float(string='Cantidad', required=True, default=1)
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida', required=True, default=lambda self: self.env.ref('uom.product_uom_unit'))
    pricelist_id = fields.Many2one('product.pricelist', string='Lista nativa', required=True, check_company=True)
    currency_id = fields.Many2one(related='pricelist_id.currency_id', string='Moneda')
    user_id = fields.Many2one('res.users', string='Vendedor evaluado', required=True, default=lambda self: self.env.user)
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Posición fiscal', check_company=True)
    date = fields.Date(string='Fecha de valoración', required=True, default=fields.Date.today)
    requested_price = fields.Monetary(string='Precio neto solicitado (sin impuestos)')
    use_requested = fields.Boolean(string='Evaluar precio solicitado')
    preferred = fields.Monetary(readonly=True, string='Precio preferente')
    min_price = fields.Monetary(readonly=True, string='Mínimo vendedor')
    margin_result = fields.Float(readonly=True, string='Margen (%)', groups='soles_pricing.group_cost')
    cost_result = fields.Monetary(readonly=True, string='Costo', groups='soles_pricing.group_cost')
    result = fields.Text(readonly=True, string='Detalle de evaluación')
    preview_rule_id = fields.Many2one('soles.pricing.rule', string='Previsualizar regla sin publicar', check_company=True, groups='soles_pricing.group_config,soles_pricing.group_publisher')

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner(self):
        if self.partner_id and self.company_id:
            partner = self.partner_id.with_company(self.company_id)
            self.pricelist_id = partner.property_product_pricelist
            self.fiscal_position_id = partner.property_account_position_id

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    def action_simulate(self):
        self.ensure_one()
        self.check_access('write')
        if self.company_id not in self.env.companies:
            raise UserError(_('Seleccione una compañía permitida.'))
        self.partner_id.check_access('read')
        self.product_id.check_access('read')
        self.pricelist_id.check_access('read')
        if self.sudo().preview_rule_id and not (self.env.user.has_group('soles_pricing.group_config') or self.env.user.has_group('soles_pricing.group_publisher')):
            raise AccessError(_('Solo un editor/publicador puede previsualizar borradores.'))
        ev = self.env['soles.pricing.engine']._evaluate(
            company=self.company_id, partner=self.partner_id, product=self.product_id,
            qty=self.quantity, uom=self.uom_id, currency=self.currency_id,
            pricelist=self.pricelist_id, date=self.date, user=self.user_id,
            taxes=self.fiscal_position_id.map_tax(self.product_id.taxes_id._filter_taxes_by_company(self.company_id)), fiscal_position=self.fiscal_position_id,
            requested=self.requested_price if self.use_requested else None, preview_ids=self.sudo().preview_rule_id.ids)
        base_rule = self.env['soles.pricing.rule'].browse(ev['base_rule_id'])
        benefit_rule = self.env['soles.pricing.rule'].browse(ev['benefit_rule_id'])
        route, users = self.env['soles.pricing.engine']._approval_route(company=self.company_id, partner=self.partner_id,
            product=self.product_id, currency=self.currency_id, ev=ev, requester=self.env.user, seller=self.user_id)
        segment = self.partner_id.with_company(self.company_id).commercial_partner_id.soles_segment_id
        version = self.env['soles.pricing.version'].browse(ev['base_version_id'])
        detail = [
            _('Segmento: %s', segment.display_name or _('Sin segmento')),
            _('Moneda: %s · fecha: %s', self.currency_id.name, str(self.date)),
            _('Base: %.4f', ev['base']), _('Beneficio: %.4f%%', ev['benefit']),
            _('Regla base: %s', base_rule.display_name or _('Nativa')),
            _('Versión: %s', str(version.revision) if version else _('Referencia nativa capturada')),
            _('Regla beneficio: %s', benefit_rule.display_name or _('Ninguna')),
            _('Facultad adicional: %.4f%%', ev['allowed']), _('Adicional solicitado: %.4f%%', ev['extra']),
            '; '.join(ev['reasons']) or _('Dentro de facultades'),
        ]
        if ev['needs_approval']:
            detail += [_('Ruta: %s', route.display_name or _('Sin ruta elegible')),
                       _('Responsables: %s', ', '.join(users.mapped('name')) or _('Configurar responsables con facultad suficiente')),
                       _('La simulación considera esta línea; una cotización valida también el importe acumulado.')]
        values = dict(preferred=ev['preferred'], min_price=ev['min_price'], result='\n'.join(detail))
        if self.env.user.has_group('soles_pricing.group_cost'):
            values.update(margin_result=ev['margin'], cost_result=ev['cost'])
        self.write(values)
        return {'type': 'ir.actions.act_window', 'name': _('Simulador de precios'), 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}


class Policy(models.TransientModel):
    _name = 'soles.pricing.policy'
    _description = 'Configurar política de precios de la compañía activa'

    company_id = fields.Many2one('res.company', string='Compañía activa', required=True, default=lambda self: self.env.company, readonly=True)
    mode = fields.Selection([('off', 'Nativo'), ('audit', 'Comparación'), ('enforce', 'Control activo')], string='Modo de operación', required=True)
    discount_mode = fields.Selection([('additive', 'Sumados sobre la base'), ('sequential', 'Sucesivos')], string='Combinación de descuentos', required=True)
    min_margin = fields.Float(string='Piso de margen sobre venta (%)')
    require_cost = fields.Boolean(string='Exigir costo positivo')
    allow_self = fields.Boolean(string='Permitir autoaprobación')
    hours = fields.Float(string='Vigencia de aprobación (horas)')
    notify_reviewers = fields.Boolean(string='Crear actividades para aprobadores elegibles')
    allow_benefit = fields.Boolean(string='Permitir beneficio adicional a la regla base')
    revalidate_cost = fields.Boolean(string='Reevaluar costo publicado al confirmar')
    fx_mode = fields.Selection([('commercial', 'Comercial publicado'), ('native', 'Contable nativo')], required=True, string='Tipo de cambio')

    brand_field_id = fields.Many2one('ir.model.fields', string='Campo de marca existente (opcional)', domain="[('model','in',['product.template','product.product']), ('ttype','=','many2one')]")

    def default_get(self, names):
        require_config(self.env)
        values = super().default_get(names)
        c = self.env.company
        mapping = {'mode': c.soles_pricing_mode, 'discount_mode': c.soles_discount_mode,
                   'min_margin': c.soles_min_margin, 'require_cost': c.soles_require_cost,
                   'allow_self': c.soles_allow_self_approval, 'hours': c.soles_approval_hours,
                   'notify_reviewers': c.soles_notify_reviewers, 'allow_benefit': c.soles_allow_benefit,
                   'revalidate_cost': c.soles_revalidate_cost, 'fx_mode': c.soles_fx_mode, 'brand_field_id': c.soles_brand_field_id.id}
        values.update({k: v for k, v in mapping.items() if k in names})
        return values

    def action_apply(self):
        self.ensure_one()
        require_config(self.env)
        self.check_access('write')
        if self.company_id != self.env.company:
            raise UserError(_('Cambie a la compañía que quiere configurar.'))
        self.company_id.sudo().write({'soles_pricing_mode': self.mode, 'soles_discount_mode': 'sequential',
                                      'soles_min_margin': self.min_margin, 'soles_require_cost': self.require_cost,
                                      'soles_allow_self_approval': self.allow_self, 'soles_approval_hours': self.hours,
                                      'soles_notify_reviewers': self.notify_reviewers, 'soles_allow_benefit': self.allow_benefit,
                                      'soles_revalidate_cost': self.revalidate_cost, 'soles_fx_mode': self.fx_mode, 'soles_brand_field_id': self.brand_field_id.id})
        return {'type': 'ir.actions.act_window_close'}


class AdvancePayment(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _create_invoices(self, sale_orders):
        # A Python identity token cannot be forged by an RPC JSON context. Native
        # down payments have zero ordered quantity and no commercial price change.
        trusted = self.with_context(_soles_native_downpayment=_NATIVE_DOWNPAYMENT)
        return super(AdvancePayment, trusted)._create_invoices(sale_orders)
