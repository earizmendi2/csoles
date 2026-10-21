from odoo import fields, models, _
from odoo.exceptions import UserError
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

    def action_simulate(self):
        self.ensure_one()
        self.check_access('write')
        if self.company_id not in self.env.companies:
            raise UserError(_('Seleccione una compañía permitida.'))
        self.partner_id.check_access('read')
        self.product_id.check_access('read')
        self.pricelist_id.check_access('read')
        ev = self.env['soles.pricing.engine']._evaluate(
            company=self.company_id, partner=self.partner_id, product=self.product_id,
            qty=self.quantity, uom=self.uom_id, currency=self.currency_id,
            pricelist=self.pricelist_id, date=self.date, user=self.user_id,
            taxes=self.fiscal_position_id.map_tax(self.product_id.taxes_id._filter_taxes_by_company(self.company_id)), fiscal_position=self.fiscal_position_id,
            requested=self.requested_price if self.use_requested else None)
        # Neutralize inclusive taxes as evaluation expects sales taxes for native prices.
        base_rule = self.env['soles.pricing.rule'].browse(ev['base_rule_id'])
        benefit_rule = self.env['soles.pricing.rule'].browse(ev['benefit_rule_id'])
        values = dict(preferred=ev['preferred'], min_price=ev['min_price'],
                      result=_('Base: %(base).4f\nBeneficio: %(benefit).4f%%\nRegla base: %(rule)s\nRegla beneficio: %(benefit_rule)s\nAdicional solicitado: %(extra).4f%%\n%(reasons)s',
                               base=ev['base'], benefit=ev['benefit'], rule=base_rule.display_name or _('Nativa'),
                               benefit_rule=benefit_rule.display_name or _('Ninguna'), extra=ev['extra'],
                               reasons='; '.join(ev['reasons']) or _('Dentro de facultades')))
        if self.env.user.has_group('soles_pricing.group_cost'):
            values.update(margin_result=ev['margin'], cost_result=ev['cost'])
        self.write(values)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}


class Policy(models.TransientModel):
    _name = 'soles.pricing.policy'
    _description = 'Configurar política de precios de la compañía activa'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    mode = fields.Selection([('off', 'A · Nativo'), ('audit', 'B · Comparación'), ('enforce', 'C/D · Control activo')], required=True)
    discount_mode = fields.Selection([('additive', 'Sumados sobre la base'), ('sequential', 'Sucesivos')], required=True)
    min_margin = fields.Float(string='Piso de margen sobre venta (%)')
    require_cost = fields.Boolean(string='Exigir costo positivo')
    allow_self = fields.Boolean(string='Permitir autoaprobación')
    hours = fields.Float(string='Vigencia de aprobación (horas)')

    def default_get(self, names):
        require_config(self.env)
        values = super().default_get(names)
        c = self.env.company
        mapping = {'mode': c.soles_pricing_mode, 'discount_mode': c.soles_discount_mode,
                   'min_margin': c.soles_min_margin, 'require_cost': c.soles_require_cost,
                   'allow_self': c.soles_allow_self_approval, 'hours': c.soles_approval_hours}
        values.update({k: v for k, v in mapping.items() if k in names})
        return values

    def action_apply(self):
        self.ensure_one()
        require_config(self.env)
        self.check_access('write')
        if self.company_id != self.env.company:
            raise UserError(_('Cambie a la compañía que quiere configurar.'))
        self.company_id.sudo().write({'soles_pricing_mode': self.mode, 'soles_discount_mode': self.discount_mode,
                                      'soles_min_margin': self.min_margin, 'soles_require_cost': self.require_cost,
                                      'soles_allow_self_approval': self.allow_self, 'soles_approval_hours': self.hours})
        return {'type': 'ir.actions.act_window_close'}


class AdvancePayment(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _create_invoices(self, sale_orders):
        # A Python identity token cannot be forged by an RPC JSON context. Native
        # down payments have zero ordered quantity and no commercial price change.
        trusted = self.with_context(_soles_native_downpayment=_NATIVE_DOWNPAYMENT)
        return super(AdvancePayment, trusted)._create_invoices(sale_orders)
