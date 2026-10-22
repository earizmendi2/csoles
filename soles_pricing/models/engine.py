from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .math import cost_price, net_price, extra_discount, margin, finite
from .governance import FX_TOKEN


class Engine(models.AbstractModel):
    _name = 'soles.pricing.engine'
    _description = 'Motor único de evaluación de precios'

    def _candidates(self, model, company, partner, product, qty, date, currency=None, preview_ids=None):
        domain = [('company_id', '=', company.id), ('active', '=', True)]
        if 'state' in self.env[model]._fields:
            domain += ['|', ('state', '=', 'published'), ('id', 'in', preview_ids or [])]
        records = self.env[model].sudo().with_company(company).search(domain)
        if preview_ids and 'series_key' in records._fields:
            series = records.filtered(lambda r: r.id in preview_ids).mapped('series_key')
            records = records.filtered(lambda r: r.id in preview_ids or r.series_key not in series)
        return records.filtered(lambda r: r._matches(partner, product, qty, date) and
                                (not r.quote_currency_id or r.quote_currency_id == currency)).sorted(key=lambda r: r._rank())

    def _authority(self, operation, user, company, partner, product, qty, date, currency=None):
        records = self._candidates('soles.pricing.authority', company, partner, product, qty, date, currency)
        return records.filtered(lambda r: r.operation == operation and (r.user_id == user or (r.group_id and r.group_id in user.sudo().groups_id)))[:1]

    def _fx_convert(self, amount, from_currency, to_currency, company, date):
        if from_currency == to_currency:
            return amount, []
        versions = []
        def factor(currency):
            if currency == company.currency_id:
                return 1.0
            rate = self.env['soles.pricing.fx'].sudo().search([
                ('company_id', '=', company.id), ('currency_id', '=', currency.id), ('state', '=', 'published'),
                ('active', '=', True), ('date_start', '<=', date), '|', ('date_end', '=', False), ('date_end', '>=', date)], limit=1)
            if not rate:
                raise ValidationError(_('Falta tipo de cambio comercial publicado para %s.', currency.name))
            versions.append(('soles.pricing.version', rate.version_id.id, str(rate.published_at)))
            return rate.rate
        return amount * factor(from_currency) / factor(to_currency), versions

    def _convert(self, amount, from_currency, to_currency, company, date):
        if company.soles_fx_mode == 'commercial':
            return self._fx_convert(amount, from_currency, to_currency, company, date)
        return from_currency._convert(amount, to_currency, company, date, round=False), []

    def _cost(self, company, product, uom, currency, date):
        cost = self.env['soles.pricing.cost'].sudo().search([
            ('company_id', '=', company.id), ('product_id', '=', product.id), ('active', '=', True),
            ('state', '=', 'published'), ('date_start', '<=', date), '|', ('date_end', '=', False), ('date_end', '>=', date)], limit=1)
        if not cost:
            return 0.0, False, False, []
        value, versions = self._convert(cost.amount + cost.freight + cost.other, cost.currency_id, currency, company, date)
        versions.append(('soles.pricing.version', cost.version_id.id, str(cost.published_at)))
        return product.uom_id._compute_price(value, uom), cost.id, cost.version_id.id, versions

    def _evaluate(self, *, company, partner, product, qty, uom, currency, pricelist, date, user,
                  taxes, fiscal_position, requested=None, snapshot=None, preview_ids=None):
        product = product.sudo().with_company(company)
        partner = partner.sudo().with_company(company)
        date = fields.Date.to_date(date)
        if not product or not finite(qty) or qty <= 0 or not uom or uom.category_id != product.uom_id.category_id:
            raise ValidationError(_('Cantidad positiva, producto y unidad de medida compatible requeridos.'))
        qty_base = uom._compute_quantity(qty, product.uom_id, round=False)
        family = product.soles_family_id
        classification = product.soles_product_policy_id
        hard_reasons = []
        if not classification or not classification.active or not classification.allow_sale:
            hard_reasons.append(_('Producto sin clasificación comercial autorizada para venta'))
        if family and not family.active:
            hard_reasons.append(_('Familia comercial inactiva'))
        commercial = dict(snapshot or {})
        if not commercial:
            rules = self._candidates('soles.pricing.rule', company, partner, product, qty_base, date, currency, preview_ids)
            base_rule = rules.filtered(lambda r: r.stage == 'base')[:1]
            allow_benefit = company.soles_allow_benefit
            if family and family.benefit_policy != 'inherit':
                allow_benefit = family.benefit_policy == 'allow'
            benefit_rule = rules.filtered(lambda r: r.stage == 'benefit')[:1] if allow_benefit else self.env['soles.pricing.rule']
            cost, cost_id, cost_version, versions = self._cost(company, product, uom, currency, date)
            method = base_rule.method if base_rule else family.method if family else 'native'
            if method == 'native':
                if not pricelist:
                    raise ValidationError(_('Seleccione una lista nativa.'))
                raw = pricelist.sudo().with_company(company).with_context(_soles_fx=FX_TOKEN)._get_product_price(
                    product.with_context(_soles_fx=FX_TOKEN), qty, uom=uom, date=date, currency=currency.with_context(_soles_fx=FX_TOKEN))
            elif method == 'list':
                raw = product._price_compute('list_price', uom=uom, company=company, date=date)[product.id]
                raw, fx = self._convert(raw, product.currency_id, currency, company, date)
                versions += fx
            elif method == 'fixed':
                raw, fx = self._convert(base_rule.fixed_price, base_rule.currency_id, currency, company, date)
                raw = product.uom_id._compute_price(raw, uom)
                versions += fx
            else:
                raw = cost_price(cost, base_rule.rate if base_rule else family.target_margin, method)
            if method in ('native', 'list'):
                mapped = product._get_tax_included_unit_price_from_price(raw, product_taxes=product.taxes_id._filter_taxes_by_company(company), fiscal_position=fiscal_position)
                raw = taxes.with_context(round=False).compute_all(mapped, currency=currency, quantity=1, product=product, partner=partner)['total_excluded']
            base = raw * (1 - (base_rule.discount_pct if base_rule else 0) / 100)
            benefit = benefit_rule.discount_pct if benefit_rule else 0
            preferred = net_price(base, benefit, mode='sequential')
            company_factor, fx = self._convert(1, currency, company.currency_id, company, date)
            versions += fx
            versions += [('soles.pricing.version', r.version_id.id, str(r.published_at)) for r in base_rule | benefit_rule]
            # Freeze native references too, without making their later edits rewrite the quote.
            versions += [(r._name, r.id, str(r.write_date)) for records in (product, product.product_tmpl_id, pricelist.sudo(), pricelist.sudo().item_ids) for r in records]
            commercial = dict(base=base, preferred=preferred, benefit=benefit, cost=cost,
                cost_id=cost_id, cost_version_id=cost_version, base_rule_id=base_rule.id or False,
                benefit_rule_id=benefit_rule.id or False, base_version_id=base_rule.version_id.id or False,
                benefit_version_id=benefit_rule.version_id.id or False, company_factor=company_factor,
                price_floor=max(company.soles_min_margin, family.min_margin if family else 0,
                                base_rule.min_margin if base_rule else 0, benefit_rule.min_margin if benefit_rule else 0),
                versions=versions, family_id=family.id or False, method=method,
                segment_id=partner.commercial_partner_id.soles_segment_id.id or False,
                evaluated_date=str(date))
        elif company.soles_revalidate_cost:
            cost, cost_id, cost_version, versions = self._cost(company, product, uom, currency, fields.Date.today())
            commercial.update(cost=cost, cost_id=cost_id, cost_version_id=cost_version)
            commercial['versions'] = list(commercial.get('versions', [])) + versions
        base, preferred, benefit, cost = [commercial[k] for k in ('base', 'preferred', 'benefit', 'cost')]
        price = preferred if requested is None else requested
        if not finite(base, preferred, price, cost) or base < 0 or price < 0:
            raise ValidationError(_('Precio o costo no válido.'))
        if company.soles_require_cost and (not commercial['cost_id'] or cost <= 0):
            hard_reasons.append(_('Falta costo comercial positivo publicado'))
        if price <= 0:
            hard_reasons.append(_('Precio neto debe ser positivo'))
        reference_company = uom._compute_price(base, product.uom_id) * commercial['company_factor']
        if classification and reference_company <= classification.minimum_reference and not (classification.require_approval and classification.allow_missing_reference):
            hard_reasons.append(_('Referencia no supera el mínimo autorizado de la clasificación'))
        authority = self._authority('discount', user, company, partner, product, qty_base, fields.Date.today(), currency)
        floor = max(commercial['price_floor'], company.soles_min_margin, family.min_margin if family else 0)
        exception_floor = family.exception_margin if family else 0
        actual_margin = margin(price, cost)
        extra = extra_discount(base, benefit, price, 'sequential')
        allowed = authority.max_discount if authority else 0
        monetary = max(0, preferred - price) * qty * commercial['company_factor']
        order_amount = price * qty * commercial['company_factor']
        percentage_minimum = preferred * (1 - allowed / 100)
        seller_floor = max(floor, authority.min_margin if authority else 0)
        minimum = max(percentage_minimum, cost / (1 - seller_floor / 100)) if cost > 0 else percentage_minimum
        reasons = list(hard_reasons)
        if currency.compare_amounts(price, percentage_minimum) < 0:
            reasons.append(_('Descuento superior a facultad del vendedor'))
        if actual_margin + 1e-8 < max(floor, authority.min_margin if authority else 0):
            reasons.append(_('Margen inferior al piso permitido'))
        if actual_margin + 1e-8 < exception_floor:
            hard_reasons.append(_('Margen inferior al mínimo excepcional absoluto de la familia'))
            reasons.append(hard_reasons[-1])
        if classification and classification.require_approval:
            reasons.append(_('Clasificación comercial requiere autorización por operación'))
        if authority and authority.limit_discount_amount and monetary > authority.max_discount_amount + 1e-8:
            reasons.append(_('Descuento monetario superior a facultad'))
        if authority and authority.limit_order_amount and order_amount > authority.max_order_amount + 1e-8:
            reasons.append(_('Importe de operación superior a facultad'))
        limits = self._candidates('soles.pricing.limit', company, partner, product, qty_base, date, currency)
        manufacturer_override = False
        minimum_commercial = 0
        limit_versions = []
        for limit in limits:
            minimum_value, fx = self._convert(limit.minimum_price, limit.currency_id, currency, company, date)
            minimum_value = product.uom_id._compute_price(minimum_value, uom)
            minimum_commercial = max(minimum_commercial, minimum_value)
            limit_versions += fx + [('soles.pricing.version', limit.version_id.id, str(limit.published_at))]
            if currency.compare_amounts(price, minimum_value) < 0:
                message = _('Precio inferior a restricción comercial: %s', limit.name)
                reasons.append(message)
                if limit.overridable:
                    manufacturer_override = True
                else:
                    hard_reasons.append(message)
        versions = list(commercial['versions']) + limit_versions
        versions += [(r._name, r.id, str(r.write_date)) for records in (authority, company.sudo(), user.sudo(), taxes.sudo(), partner.commercial_partner_id, classification, family) for r in records]
        return dict(commercial= commercial, base=base, preferred=preferred, benefit=benefit, requested=price, cost=cost,
                    margin=actual_margin, floor=floor, exception_floor=exception_floor, extra=extra, allowed=allowed,
                    min_price=max(minimum, minimum_commercial), minimum_commercial=minimum_commercial,
                    base_rule_id=commercial['base_rule_id'], benefit_rule_id=commercial['benefit_rule_id'],
                    base_version_id=commercial.get('base_version_id'), cost_version_id=commercial.get('cost_version_id'),
                    authority_id=authority.id or False, cost_id=commercial['cost_id'],
                    company_factor=commercial['company_factor'], discount_amount_company=monetary, order_amount_company=order_amount,
                    manual_approval=bool(classification and classification.require_approval),
                    manufacturer_override=manufacturer_override, allow_b2b=bool(classification and classification.allow_b2b),
                    versions=versions, qty_base=qty_base, reasons=list(dict.fromkeys(reasons)),
                    hard_reasons=list(dict.fromkeys(hard_reasons)), needs_approval=bool(reasons))

    def _approval_authority(self, *, user, company, partner, product, currency, ev, requester, seller):
        """Shared qualification used by routing, simulation and confirmation."""
        empty = self.env['soles.pricing.authority']
        if not user.active or not user.has_group('soles_pricing.group_approver') or company not in user.company_ids:
            return empty
        if not company.soles_allow_self_approval and user in (requester | seller):
            return empty
        if ev['hard_reasons']:
            return empty
        authority = self._authority('approve', user, company, partner, product, ev['qty_base'], fields.Date.today(), currency)
        if not authority:
            return empty
        floor = max(authority.min_margin, ev['exception_floor'])
        if not authority.override_floor:
            floor = max(floor, ev['floor'])
        if ev['extra'] > authority.max_discount + 1e-8 or ev['margin'] + 1e-8 < floor:
            return empty
        if authority.limit_discount_amount and ev.get('quote_discount_company', ev['discount_amount_company']) > authority.max_discount_amount + 1e-8:
            return empty
        if authority.limit_order_amount and ev.get('quote_amount_company', ev['order_amount_company']) > authority.max_order_amount + 1e-8:
            return empty
        if ev['manual_approval'] and not authority.allow_manual_quote:
            return empty
        if ev['manufacturer_override'] and not authority.override_manufacturer:
            return empty
        return authority

    def _approval_route(self, *, company, partner, product, currency, ev, requester, seller):
        routes = self._candidates('soles.pricing.route', company, partner, product, ev['qty_base'], fields.Date.today(), currency)
        for route in routes:
            amount = ev.get('quote_discount_company', ev['discount_amount_company'])
            if amount < route.min_discount_amount or (route.max_discount_amount and amount > route.max_discount_amount):
                continue
            candidates = route.reviewer_ids | route.reviewer_group_id.users
            users = candidates.filtered(lambda u: not u.share and self._approval_authority(user=u, company=company, partner=partner,
                product=product, currency=currency, ev=ev, requester=requester, seller=seller))
            if users:
                return route, users
        return self.env['soles.pricing.route'], self.env['res.users']

    @api.model
    def get_customer_price(self, partner_id, product_id, quantity=1, pricelist_id=None):
        """Authenticated internal facade; a future B2B adapter must authenticate its customer."""
        if not self.env.user.has_group('sales_team.group_sale_salesman'):
            raise AccessError(_('Consulta comercial reservada a usuarios autorizados.'))
        partner = self.env['res.partner'].browse(partner_id).exists()
        product = self.env['product.product'].browse(product_id).exists()
        partner.check_access('read')
        product.check_access('read')
        if not partner or not product:
            raise ValidationError(_('Cliente y producto requeridos.'))
        pricelist = self.env['product.pricelist'].browse(pricelist_id) if pricelist_id else partner.property_product_pricelist
        pricelist.check_access('read')
        company = self.env.company
        for record in (partner, product, pricelist):
            if record.company_id and record.company_id != company:
                raise AccessError(_('Documento de otra compañía.'))
        position = partner.property_account_position_id
        ev = self._evaluate(company=company, partner=partner, product=product, qty=quantity, uom=product.uom_id,
                            currency=pricelist.currency_id, pricelist=pricelist, date=fields.Date.today(), user=self.env.user,
                            taxes=position.map_tax(product.taxes_id._filter_taxes_by_company(company)), fiscal_position=position)
        keys = ['base', 'preferred', 'min_price', 'allowed', 'base_rule_id', 'base_version_id', 'allow_b2b', 'needs_approval', 'reasons']
        if self.env.user.has_group('soles_pricing.group_cost'):
            keys += ['cost', 'margin']
        return {k: ev[k] for k in keys}
