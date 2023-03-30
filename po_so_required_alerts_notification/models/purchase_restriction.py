from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        if not self.order_line:
            raise ValidationError(_('Alert!!,  Mr.%s , You cannot confirm Purchase Order %s which has No Order line.'
                                    % (self.env.user.name, self.name)))
        else:
            for line in self.order_line:
                if line.price_unit == 0.00:
                    raise ValidationError(
                        _('Alert!!,  Mr.%s , You cannot confirm a Purchase Order %s The Unit Price Should be '
                          'Greater than Zero for the Product %s. '
                          % (self.env.user.name, self.name, line.name)))
                elif line.product_uom_qty == 0.00:
                    raise ValidationError(
                        _('Alert!!,  Mr.%s , You cannot confirm a Purchase Order %s The Order Qty Should be '
                          'Greater than Zero for the Product %s. '
                          % (self.env.user.name, self.name, line.name)))
        return res


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        if not self.order_line:
            raise ValidationError(_('Alert!!,  Mr.%s , You cannot confirm Sale Order %s which has No Order line.'
                                    % (self.env.user.name, self.name)))
        else:
            for line in self.order_line:
                if line.price_unit == 0.00:
                    raise ValidationError(
                        _('Alert!!,  Mr.%s , You cannot confirm a Sale Order %s The Unit Price Should be '
                          'Greater than Zero for the Product %s. '
                          % (self.env.user.name, self.name, line.name)))
                elif line.product_uom_qty == 0.00:
                    raise ValidationError(
                        _('Alert!!,  Mr.%s , You cannot confirm a Sale Order %s The Order Qty Should be '
                          'Greater than Zero for the Product %s. '
                          % (self.env.user.name, self.name, line.name)))

        return res
