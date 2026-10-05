import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    allowed_warehouse_ids_ui = fields.Many2many(
        comodel_name="stock.warehouse",
        compute="_compute_allowed_warehouse_ids_ui",
        string="Almacenes permitidos para el usuario actual",
    )
    warehouse_restriction_active = fields.Boolean(
        compute="_compute_allowed_warehouse_ids_ui",
        string="Restricción de almacén activa",
    )

    @api.depends("company_id")
    def _compute_allowed_warehouse_ids_ui(self):
        current_user = self.env.user
        restriction_active = current_user._sale_warehouse_restriction_is_active()

        unrestricted_by_company = {}
        for order in self:
            company = order.company_id or self.env.company
            order.warehouse_restriction_active = restriction_active

            if restriction_active:
                order.allowed_warehouse_ids_ui = current_user._get_allowed_sale_warehouses(
                    company
                )
            else:
                if company.id not in unrestricted_by_company:
                    unrestricted_by_company[company.id] = self.env[
                        "stock.warehouse"
                    ].search(
                        [
                            ("company_id", "=", company.id),
                            ("active", "=", True),
                        ]
                    )
                order.allowed_warehouse_ids_ui = unrestricted_by_company[company.id]

    def _check_current_user_sale_warehouse_access(self, operation=None):
        current_user = self.env.user
        if not current_user._sale_warehouse_restriction_is_active():
            return

        for order in self:
            company = order.company_id or self.env.company
            allowed_warehouses = current_user._get_allowed_sale_warehouses(company)

            if not order.warehouse_id:
                continue

            if order.warehouse_id not in allowed_warehouses:
                _logger.warning(
                    "Blocked sale warehouse operation. user_id=%s order_id=%s "
                    "warehouse_id=%s company_id=%s operation=%s",
                    current_user.id,
                    order.id,
                    order.warehouse_id.id,
                    company.id,
                    operation or "unspecified",
                )

                if allowed_warehouses:
                    allowed_names = ", ".join(
                        allowed_warehouses.mapped("display_name")
                    )
                    raise UserError(
                        _(
                            "No tienes autorización para vender desde el almacén "
                            "'%(warehouse)s'.\n\nTus almacenes autorizados para %(company)s son: "
                            "%(allowed)s.\n\nSi necesitas acceso adicional, solicítalo al "
                            "Departamento de Sistemas.",
                            warehouse=order.warehouse_id.display_name,
                            company=company.display_name,
                            allowed=allowed_names,
                        )
                    )

                raise UserError(
                    _(
                        "No tienes ningún almacén autorizado para realizar ventas en "
                        "%(company)s. Solicita al Departamento de Sistemas que configure "
                        "tus almacenes permitidos.",
                        company=company.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._check_current_user_sale_warehouse_access(operation="create")
        return orders

    def write(self, vals):
        result = super().write(vals)

        relevant_fields = {"warehouse_id", "company_id", "user_id"}
        if relevant_fields.intersection(vals):
            self._check_current_user_sale_warehouse_access(operation="write")

        return result

    def _action_confirm(self):
        self._check_current_user_sale_warehouse_access(operation="confirm")
        return super()._action_confirm()
