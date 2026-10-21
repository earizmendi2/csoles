from odoo import models, _
from odoo.exceptions import ValidationError
from .math import cost_price, net_price, extra_discount, margin, finite


class Engine(models.AbstractModel):
    _name = 'soles.pricing.engine'
    _description = 'Motor único de evaluación de precios'

    def _candidates(self, model, company, partner, product, qty, date):
        records = self.env[model].sudo().with_company(company).search([('company_id', '=', company.id), ('active', '=', True)])
        return records.filtered(lambda r: r._matches(partner, product, qty, date)).sorted(key=lambda r: r._rank())

    def _authority(self, operation, user, company, partner, product, qty, date):
        records = self._candidates('soles.pricing.authority', company, partner, product, qty, date)
        records = records.filtered(lambda r: r.operation == operation and (r.user_id == user or (r.group_id and r.group_id in user.sudo().groups_id)))
        # At equal explicit priority a user override precedes all role assignments.
        return records.sorted(key=lambda r: (r.sequence, not bool(r.user_id), *r._rank()[1:]))[:1]

    def _evaluate(self, *, company, partner, product, qty, uom, currency, pricelist, date, user, taxes, fiscal_position, requested=None):
        product = product.sudo().with_company(company)
        if not finite(qty) or qty <= 0 or uom.category_id != product.uom_id.category_id:
            raise ValidationError(_('Cantidad positiva y unidad de medida compatible requeridas.'))
        qty_base = uom._compute_quantity(qty, product.uom_id, round=False)
        rules = self._candidates('soles.pricing.rule', company, partner, product, qty_base, date)
        base_rule = rules.filtered(lambda r: r.stage == 'base')[:1]
        benefit_rule = rules.filtered(lambda r: r.stage == 'benefit')[:1]
        costs = self.env['soles.pricing.cost'].sudo().search([
            ('company_id', '=', company.id), ('product_id', '=', product.id), ('active', '=', True),
            ('date_start', '<=', date), '|', ('date_end', '=', False), ('date_end', '>=', date)], limit=1)
        if costs:
            cost = costs.currency_id._convert(costs.amount + costs.freight + costs.other, currency, company, date, round=False)
        else:
            cost = company.currency_id._convert(product.standard_price, currency, company, date, round=False)
        cost = product.uom_id._compute_price(cost, uom)
        method = base_rule.method if base_rule else 'native'
        # Native/list product prices follow Odoo's product-tax basis. Fixed and cost
        # formulas explicitly represent tax-exclusive commercial values.
        if method == 'native':
            if not pricelist:
                raise ValidationError(_('Seleccione una lista de precios nativa.'))
            raw = pricelist.sudo().with_company(company)._get_product_price(product, qty, uom=uom, date=date, currency=currency)
        elif method == 'list':
            raw = product._price_compute('list_price', uom=uom, currency=currency, company=company, date=date)[product.id]
        elif method == 'fixed':
            raw = base_rule.currency_id._convert(base_rule.fixed_price, currency, company, date, round=False)
            raw = product.uom_id._compute_price(raw, uom)
        else:
            raw = cost_price(cost, base_rule.rate, method)
        if method in ('native', 'list'):
            mapped = product._get_tax_included_unit_price_from_price(raw, product_taxes=product.taxes_id._filter_taxes_by_company(company), fiscal_position=fiscal_position)
            raw = taxes.compute_all(mapped, currency=currency, quantity=1, product=product, partner=partner)['total_excluded']
        base = raw * (1 - (base_rule.discount_pct if base_rule else 0) / 100)
        benefit = benefit_rule.discount_pct if benefit_rule else 0
        preferred = net_price(base, benefit, mode=company.soles_discount_mode)
        price = preferred if requested is None else requested
        if not finite(base, preferred, price, cost) or base < 0 or price < 0:
            raise ValidationError(_('Precio o costo no válido.'))
        authority = self._authority('discount', user, company, partner, product, qty_base, date)
        floor = max(company.soles_min_margin, base_rule.min_margin if base_rule else 0, benefit_rule.min_margin if benefit_rule else 0)
        allowed = authority.max_discount if authority else 0
        if company.soles_discount_mode == 'additive':
            allowed = min(allowed, 100 - benefit)
        auth_floor = max(floor, authority.min_margin if authority else 0)
        extra = extra_discount(base, benefit, price, company.soles_discount_mode)
        actual_margin = margin(price, cost)
        reasons = []
        if company.soles_require_cost and cost <= 0:
            reasons.append(_('Falta costo comercial positivo'))
        if price <= 0:
            reasons.append(_('Precio neto debe ser positivo'))
        if currency.compare_amounts(price, net_price(base, benefit, allowed, company.soles_discount_mode)) < 0:
            reasons.append(_('Descuento superior a facultad del vendedor'))
        if actual_margin + 1e-8 < auth_floor:
            reasons.append(_('Margen inferior al piso permitido'))
        versions = [(r._name, r.id, str(r.write_date)) for r in (base_rule | benefit_rule)]
        versions += [(r._name, r.id, str(r.write_date)) for r in costs | self.env['soles.pricing.cost']]
        versions += [(r._name, r.id, str(r.write_date)) for r in authority]
        for records in (product, product.product_tmpl_id, pricelist.sudo(), pricelist.sudo().item_ids,
                        company.sudo(), user.sudo(), taxes.sudo(), partner.sudo().commercial_partner_id):
            versions += [(r._name, r.id, str(r.write_date)) for r in records]
        return dict(base=base, preferred=preferred, benefit=benefit, requested=price, cost=cost,
                    margin=actual_margin, floor=floor, extra=extra, allowed=allowed,
                    min_price=net_price(base, benefit, allowed, company.soles_discount_mode),
                    base_rule_id=base_rule.id or False, benefit_rule_id=benefit_rule.id or False,
                    authority_id=authority.id or False, cost_id=costs.id or False,
                    versions=versions, qty_base=qty_base, reasons=reasons, needs_approval=bool(reasons))
