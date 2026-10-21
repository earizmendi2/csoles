"""Pure arithmetic: all commercial parameters come from records, never constants."""
import math


def finite(*values):
    return all(math.isfinite(v) for v in values)


def cost_price(cost, rate, method):
    if not finite(cost, rate) or cost < 0 or rate < 0:
        raise ValueError('Costo o margen inválido')
    if method == 'cost_margin':
        if rate >= 100:
            raise ValueError('El margen sobre venta debe ser menor a 100%')
        return cost / (1 - rate / 100)
    return cost * (1 + rate / 100)


def net_price(base, benefit, extra=0, mode='additive'):
    if not finite(base, benefit, extra) or base < 0 or not 0 <= benefit <= 100 or not 0 <= extra <= 100:
        raise ValueError('Precio o descuento inválido')
    if mode == 'additive':
        if benefit + extra > 100:
            raise ValueError('La suma de descuentos excede 100%')
        return base * (1 - (benefit + extra) / 100)
    return base * (1 - benefit / 100) * (1 - extra / 100)


def extra_discount(base, benefit, requested, mode):
    if base <= 0:
        return 0.0 if requested >= base else 100.0
    preferred = net_price(base, benefit, mode=mode)
    denominator = base if mode == 'additive' else preferred
    return max(0.0, (preferred - requested) / denominator * 100) if denominator else 0.0


def margin(price, cost):
    return (price - cost) / price * 100 if price > 0 else -100.0
