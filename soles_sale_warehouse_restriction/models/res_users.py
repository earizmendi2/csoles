from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    restrict_sale_warehouse = fields.Boolean(
        string="Restringir almacenes en ventas",
        default=False,
        help=(
            "Si está activo, el usuario solo podrá crear, modificar y confirmar "
            "ventas usando los almacenes autorizados."
        ),
    )
    allowed_sale_warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        relation="soles_sale_warehouse_user_rel",
        column1="user_id",
        column2="warehouse_id",
        string="Almacenes de venta autorizados",
        help=(
            "Almacenes desde los que este usuario puede operar órdenes de venta. "
            "Si la restricción está activa y la lista está vacía, no podrá vender "
            "desde ningún almacén."
        ),
    )

    @api.constrains("allowed_sale_warehouse_ids", "company_ids")
    def _check_allowed_sale_warehouse_companies(self):
        for user in self:
            invalid = user.allowed_sale_warehouse_ids.filtered(
                lambda warehouse: warehouse.company_id not in user.company_ids
            )
            if invalid:
                raise ValidationError(
                    _(
                        "No puedes autorizar almacenes de compañías a las que el usuario "
                        "no tiene acceso.\n\nAlmacenes inválidos: %(warehouses)s",
                        warehouses=", ".join(invalid.mapped("display_name")),
                    )
                )

    def _can_manage_sale_warehouse_restrictions(self):
        """Indica si el usuario actual puede administrar la configuración del módulo."""
        current_user = self.env.user
        return bool(
            self.env.uid == SUPERUSER_ID
            or current_user.has_group("base.group_system")
            or current_user.has_group("base.group_erp_manager")
            or current_user.has_group(
                "soles_sale_warehouse_restriction.group_sale_warehouse_restriction_manager"
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        protected_fields = {"restrict_sale_warehouse", "allowed_sale_warehouse_ids"}
        if any(protected_fields.intersection(vals) for vals in vals_list):
            if not self._can_manage_sale_warehouse_restrictions():
                raise AccessError(
                    _(
                        "No tienes permisos para configurar restricciones de almacenes "
                        "de venta."
                    )
                )
        return super().create(vals_list)

    def write(self, vals):
        protected_fields = {"restrict_sale_warehouse", "allowed_sale_warehouse_ids"}
        if protected_fields.intersection(vals):
            if not self._can_manage_sale_warehouse_restrictions():
                raise AccessError(
                    _(
                        "No tienes permisos para modificar restricciones de almacenes "
                        "de venta."
                    )
                )
        return super().write(vals)

    def _sale_warehouse_restriction_is_active(self):
        self.ensure_one()

        if self.id == SUPERUSER_ID:
            return False
        if self.has_group("base.group_system"):
            return False
        if self.has_group("base.group_erp_manager"):
            return False
        if self.has_group(
            "soles_sale_warehouse_restriction.group_sale_warehouse_restriction_bypass"
        ):
            return False

        return bool(self.restrict_sale_warehouse)

    def _get_allowed_sale_warehouses(self, company=None):
        self.ensure_one()
        company = company or self.env.company
        return self.allowed_sale_warehouse_ids.filtered(
            lambda warehouse: warehouse.active and warehouse.company_id == company
        )

    def _get_default_warehouse_id(self):
        """Respeta el almacén predeterminado nativo, pero nunca devuelve uno no autorizado."""
        self.ensure_one()
        default_warehouse = super()._get_default_warehouse_id()

        if not self._sale_warehouse_restriction_is_active():
            return default_warehouse

        allowed_warehouses = self._get_allowed_sale_warehouses(self.env.company)
        if default_warehouse and default_warehouse in allowed_warehouses:
            return default_warehouse

        return allowed_warehouses[:1]
