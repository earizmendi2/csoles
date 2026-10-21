import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .math import finite, net_price
from .configuration import require_config


ORDER_KEYS = {'partner_id', 'partner_invoice_id', 'partner_shipping_id', 'pricelist_id', 'currency_id', 'company_id', 'user_id', 'fiscal_position_id', 'soles_pricing_date', 'date_order', 'validity_date', 'payment_term_id'}
LINE_KEYS = {'product_id', 'product_uom', 'product_uom_qty', 'price_unit', 'discount', 'tax_id', 'order_id', 'display_type', 'is_downpayment', 'combo_item_id', 'linked_line_id'}
_NATIVE_DOWNPAYMENT = object()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    soles_pricing_date = fields.Date(string='Fecha de evaluación Soles', required=True, default=fields.Date.today, copy=False)
    soles_pricing_mode = fields.Selection(related='company_id.soles_pricing_mode')
    soles_approval_ids = fields.One2many('soles.pricing.approval', 'order_id', string='Autorizaciones', copy=False)

    def _soles_lock(self):
        if self.ids:
            self.env.cr.execute('SELECT id FROM sale_order WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])

    def _soles_invalidate(self):
        self.sudo().soles_approval_ids.filtered(lambda r: r.state in ('pending', 'approved')).write({'state': 'invalid'})

    def _soles_snapshot(self):
        self.ensure_one()
        order = self.sudo().with_company(self.company_id)
        company = order.company_id
        lines = []
        for line in order.order_line.sorted('id'):
            if line.soles_native_downpayment:
                lines.append([line.id, 'native_downpayment', line.price_unit, line.product_uom_qty, line.tax_id.ids])
                continue
            if line.display_type:
                lines.append([line.id, line.display_type, line.name])
                continue
            ev = line._soles_evaluate()
            lines.append([line.id, line.product_id.id, line.product_uom.id, line.product_uom_qty,
                          line.price_unit, line.discount, line.tax_id.ids, ev])
        data = [order.id, order.partner_id.id, order.partner_invoice_id.id, order.partner_shipping_id.id,
                company.id, order.currency_id.id, order.pricelist_id.id, order.user_id.id,
                order.fiscal_position_id.id, str(order.soles_pricing_date), str(order.validity_date),
                order.payment_term_id.id, company.soles_discount_mode, company.soles_min_margin,
                company.soles_require_cost, company.soles_allow_self_approval, company.soles_approval_hours,
                lines]
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    def _soles_validate_and_consume(self):
        """Called for every draft/sent -> sale write, including direct RPC and portal."""
        for order in self:
            if order.company_id.soles_pricing_mode == 'off':
                continue
            if order.validity_date and order.validity_date < fields.Date.today():
                raise UserError(_('La cotización ha vencido. Actualice su vigencia.'))
            consumed = self.env['soles.pricing.approval'].sudo()
            findings = []
            for line in order.order_line.filtered(lambda r: not r.display_type and not r.soles_native_downpayment):
                try:
                    ev = line._soles_evaluate()
                except (ValidationError, ValueError) as exc:
                    if order.company_id.soles_pricing_mode == 'audit':
                        findings.append('%s: %s' % (line.display_name, str(exc)))
                        continue
                    raise
                if ev['needs_approval']:
                    approval = order.sudo().soles_approval_ids.filtered(lambda a: a.line_id == line and a._usable())[:1]
                    if not approval:
                        findings.append('%s: %s' % (line.product_id.display_name, '; '.join(ev['reasons'])))
                    consumed |= approval
            if order.company_id.soles_pricing_mode == 'audit':
                order.message_post(body=_('Comparación Soles: %s', '\n'.join(findings) or _('Sin desviaciones')))
                continue
            if findings:
                raise UserError(_('Requiere autorización extraordinaria:\n%s', '\n'.join(findings)))
            consumed.write({'state': 'consumed', 'consumed_at': fields.Datetime.now()})

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('state', 'draft') != 'draft' for v in vals_list):
            raise AccessError(_('Cree la cotización en borrador y confírmela mediante el flujo normal.'))
        for vals in vals_list:
            if vals.get('soles_pricing_date') and fields.Date.to_date(vals['soles_pricing_date']) != fields.Date.today():
                require_config(self.env)
        return super().create(vals_list)

    def write(self, vals):
        self.check_access('write')
        if vals.get('soles_pricing_date') and fields.Date.to_date(vals['soles_pricing_date']) != fields.Date.today():
            require_config(self.env)
        self._soles_lock()
        transitioning = self.filtered(lambda r: r.state != 'sale') if vals.get('state') == 'sale' else self.browse()
        commercial = ORDER_KEYS.intersection(vals)
        if commercial and self.filtered(lambda r: r.state == 'sale' and r.company_id.soles_pricing_mode != 'off'):
            raise UserError(_('Cancele y regrese a borrador antes de cambiar condiciones comerciales.'))
        # Validate against new commercial values on arbitrary RPC transitions;
        # Odoo's own confirmation only changes date_order, which is not the pricing date.
        if transitioning:
            if (commercial - {'date_order'}) or 'order_line' in vals:
                raise UserError(_('Guarde primero los cambios comerciales y después confirme.'))
            transitioning._soles_validate_and_consume()
        result = super().write(vals)
        if (commercial and not transitioning) or vals.get('state') in ('cancel', 'draft'):
            self._soles_invalidate()
        return result

    def action_soles_reprice(self):
        self.check_access('write')
        self._soles_lock()
        for order in self:
            if order.state not in ('draft', 'sent'):
                raise UserError(_('Solo puede recalcular cotizaciones.'))
            if order.company_id.soles_pricing_mode != 'enforce':
                raise UserError(_('Active el control Soles para aplicar precios. Use el simulador durante comparación.'))
            for line in order.order_line.filtered(lambda r: not r.display_type and not r.soles_native_downpayment):
                price = line._soles_evaluate(preferred=True)['preferred']
                line.write({'price_unit': line._soles_tax_included(price), 'discount': 0})
        return True


class SaleLine(models.Model):
    _inherit = 'sale.order.line'

    soles_base = fields.Monetary(string='Base Soles', compute='_compute_soles')
    soles_preferred = fields.Monetary(string='Precio preferente', compute='_compute_soles')
    soles_min_price = fields.Monetary(string='Mínimo vendedor', compute='_compute_soles')
    soles_extra = fields.Float(string='Descuento adicional efectivo (%)', compute='_compute_soles', inverse='_inverse_soles_extra')
    soles_cost = fields.Monetary(string='Costo comercial', compute='_compute_soles', groups='soles_pricing.group_cost')
    soles_margin = fields.Float(string='Margen (%)', compute='_compute_soles', groups='soles_pricing.group_cost')
    soles_needs_approval = fields.Boolean(string='Requiere autorización', compute='_compute_soles')
    soles_explanation = fields.Char(string='Evaluación', compute='_compute_soles')
    soles_request_reason = fields.Char(string='Motivo de excepción', copy=False)
    soles_native_downpayment = fields.Boolean(readonly=True, copy=False)

    def _soles_evaluate(self, preferred=False):
        self.ensure_one()
        line = self.sudo().with_company(self.company_id)
        order = line.order_id
        net = line.tax_id.compute_all(line.price_unit * (1 - line.discount / 100), currency=order.currency_id,
                                      quantity=1, product=line.product_id, partner=order.partner_id)['total_excluded']
        return self.env['soles.pricing.engine']._evaluate(
            company=order.company_id, partner=order.partner_id, product=line.product_id.with_context(**line._get_product_price_context()),
            qty=line.product_uom_qty, uom=line.product_uom, currency=order.currency_id,
            pricelist=order.pricelist_id, date=order.soles_pricing_date, user=order.user_id,
            taxes=line.tax_id, fiscal_position=order.fiscal_position_id, requested=None if preferred else net)

    def _soles_tax_included(self, price):
        self.ensure_one()
        # Reverse tax-exclusive -> Odoo's price_unit basis, including mapped inclusive taxes.
        taxes = self.tax_id.with_context(round=False).compute_all(
            price, currency=self.currency_id, quantity=1, product=self.product_id,
            partner=self.order_id.partner_id, handle_price_include=False)['taxes']
        included = self.tax_id.flatten_taxes_hierarchy().filtered('price_include').ids
        return price + sum(t['amount'] for t in taxes if t['id'] in included)

    def _inverse_soles_extra(self):
        for line in self:
            extra = line.soles_extra
            ev = line._soles_evaluate(preferred=True)
            try:
                price = net_price(ev['base'], ev['benefit'], extra, line.company_id.soles_discount_mode)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            line.write({'price_unit': line._soles_tax_included(price), 'discount': 0})

    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'price_unit', 'discount', 'tax_id',
                 'order_id.partner_id', 'order_id.pricelist_id', 'order_id.soles_pricing_date', 'order_id.user_id')
    def _compute_soles(self):
        for line in self:
            ev = {}
            if line.product_id and line.product_uom and not line.display_type and line.product_uom_qty > 0:
                ev = line._soles_evaluate()
            line.soles_base = ev.get('base', 0)
            line.soles_preferred = ev.get('preferred', 0)
            line.soles_min_price = ev.get('min_price', 0)
            line.soles_extra = ev.get('extra', 0)
            line.soles_cost = ev.get('cost', 0)
            line.soles_margin = ev.get('margin', 0)
            line.soles_needs_approval = ev.get('needs_approval', False)
            line.soles_explanation = '; '.join(ev.get('reasons', [])) or _('Dentro de facultades')

    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'order_id.partner_id', 'order_id.pricelist_id', 'order_id.soles_pricing_date')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if line.order_id.company_id.soles_pricing_mode == 'enforce' and line.order_id.state in ('draft', 'sent') and line.product_id and line.product_uom and line.product_uom_qty > 0:
                # Preserve manual prices, like native Odoo. Explicit reprice resets them.
                if not line.currency_id.compare_amounts(line.price_unit, line.technical_price_unit):
                    price = line._soles_tax_included(line._soles_evaluate(preferred=True)['preferred'])
                    line.price_unit = price
                    line.technical_price_unit = price

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_discount(self):
        super()._compute_discount()
        for line in self:
            if line.company_id.soles_pricing_mode == 'enforce':
                line.discount = 0

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env['sale.order'].browse(list({v['order_id'] for v in vals_list if v.get('order_id')}))
        orders.check_access('write')
        orders._soles_lock()
        trusted = self.env.context.get('_soles_native_downpayment') is _NATIVE_DOWNPAYMENT
        if any('soles_native_downpayment' in v for v in vals_list):
            raise AccessError(_('La marca de anticipo es interna.'))
        native_deposits = trusted and all(v.get('is_downpayment') and not v.get('product_uom_qty') for v in vals_list)
        if orders.filtered(lambda o: o.state == 'sale' and o.company_id.soles_pricing_mode != 'off') and not native_deposits:
            raise UserError(_('Regrese a borrador antes de agregar líneas.'))
        if native_deposits:
            vals_list = [dict(v, soles_native_downpayment=True) for v in vals_list]
        lines = super().create(vals_list)
        lines.order_id._soles_invalidate()
        return lines

    def write(self, vals):
        if 'soles_native_downpayment' in vals:
            raise AccessError(_('La marca de anticipo es interna.'))
        self.check_access('write')
        orders = self.order_id | self.env['sale.order'].browse(vals.get('order_id', []))
        orders.check_access('write')
        orders._soles_lock()
        if LINE_KEYS.intersection(vals):
            if orders.filtered(lambda o: o.state == 'sale' and o.company_id.soles_pricing_mode != 'off'):
                raise UserError(_('Regrese a borrador antes de modificar líneas comerciales.'))
            orders._soles_invalidate()
        return super().write(vals)

    def unlink(self):
        self.check_access('unlink')
        orders = self.order_id
        orders._soles_lock()
        if orders.filtered(lambda o: o.state == 'sale' and o.company_id.soles_pricing_mode != 'off'):
            raise UserError(_('No puede eliminar líneas confirmadas.'))
        orders._soles_invalidate()
        return super().unlink()

    @api.constrains('price_unit', 'discount', 'product_uom_qty')
    def _check_soles_numbers(self):
        for line in self:
            if line.company_id.soles_pricing_mode == 'off':
                continue
            if not finite(line.price_unit, line.discount, line.product_uom_qty) or not 0 <= line.discount <= 100:
                raise ValidationError(_('Precio, cantidad o descuento inválidos.'))

    def action_soles_request(self):
        self.ensure_one()
        self.check_access('write')
        order = self.order_id
        order._soles_lock()
        if order.state not in ('draft', 'sent') or self.display_type or not self.soles_request_reason:
            raise UserError(_('Guarde una cotización, seleccione una línea y escriba el motivo de excepción.'))
        ev = self._soles_evaluate()
        if not ev['needs_approval']:
            raise UserError(_('El precio ya está dentro de facultades.'))
        order.sudo().soles_approval_ids.filtered(lambda a: a.line_id == self and a.state in ('pending', 'approved')).write({'state': 'invalid'})
        approval = self.env['soles.pricing.approval'].sudo().create({
            'order_id': order.id, 'line_id': self.id, 'requester_id': self.env.user.id,
            'reason': self.soles_request_reason, 'fingerprint': order._soles_snapshot(),
            'requested_price': ev['requested'], 'requested_extra': ev['extra'],
            'cost_snapshot': ev['cost'], 'margin_snapshot': ev['margin'],
        })
        order.message_post(body=_('Solicitud extraordinaria registrada para %s.', self.product_id.display_name))
        return {'type': 'ir.actions.act_window', 'res_model': approval._name, 'res_id': approval.id, 'view_mode': 'form', 'target': 'current'}
