from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleWarehouseRestriction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.warehouse_1 = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.warehouse_2 = cls.env["stock.warehouse"].create(
            {
                "name": "Warehouse Restriction Test 2",
                "code": "WRT2",
                "company_id": cls.company.id,
            }
        )

        sale_group = cls.env.ref("sales_team.group_sale_salesman")
        internal_group = cls.env.ref("base.group_user")

        cls.restricted_user = cls.env["res.users"].create(
            {
                "name": "Restricted Sales User",
                "login": "restricted.sale.warehouse@example.test",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "groups_id": [Command.set([internal_group.id, sale_group.id])],
                "restrict_sale_warehouse": True,
                "allowed_sale_warehouse_ids": [Command.set([cls.warehouse_1.id])],
                "property_warehouse_id": cls.warehouse_1.id,
            }
        )

        cls.unrestricted_user = cls.env["res.users"].create(
            {
                "name": "Unrestricted Sales User",
                "login": "unrestricted.sale.warehouse@example.test",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "groups_id": [Command.set([internal_group.id, sale_group.id])],
                "restrict_sale_warehouse": False,
                "property_warehouse_id": cls.warehouse_1.id,
            }
        )

        cls.partner = cls.env["res.partner"].create({"name": "Warehouse Test Customer"})

    def test_restricted_user_can_create_in_allowed_warehouse(self):
        order = self.env["sale.order"].with_user(self.restricted_user).create(
            {
                "partner_id": self.partner.id,
                "warehouse_id": self.warehouse_1.id,
            }
        )
        self.assertEqual(order.warehouse_id, self.warehouse_1)

    def test_restricted_user_cannot_create_in_disallowed_warehouse(self):
        with self.assertRaises(UserError):
            self.env["sale.order"].with_user(self.restricted_user).create(
                {
                    "partner_id": self.partner.id,
                    "warehouse_id": self.warehouse_2.id,
                }
            )

    def test_restricted_user_cannot_change_to_disallowed_warehouse(self):
        order = self.env["sale.order"].with_user(self.restricted_user).create(
            {
                "partner_id": self.partner.id,
                "warehouse_id": self.warehouse_1.id,
            }
        )
        with self.assertRaises(UserError):
            order.with_user(self.restricted_user).write(
                {"warehouse_id": self.warehouse_2.id}
            )

    def test_confirmation_revalidates_warehouse(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "warehouse_id": self.warehouse_2.id,
                "user_id": self.restricted_user.id,
            }
        )
        with self.assertRaises(UserError):
            order.with_user(self.restricted_user)._action_confirm()

    def test_disallowed_default_warehouse_does_not_bypass_restriction(self):
        # sale_stock allows users to modify their own default warehouse. Even if
        # they point it to a disallowed warehouse, our default resolver must fall
        # back to an authorized warehouse.
        self.restricted_user.with_user(self.restricted_user).with_company(
            self.company
        ).write({"property_warehouse_id": self.warehouse_2.id})

        order = self.env["sale.order"].with_user(self.restricted_user).create(
            {"partner_id": self.partner.id}
        )
        self.assertEqual(order.warehouse_id, self.warehouse_1)

    def test_unrestricted_user_can_use_any_company_warehouse(self):
        order = self.env["sale.order"].with_user(self.unrestricted_user).create(
            {
                "partner_id": self.partner.id,
                "warehouse_id": self.warehouse_2.id,
            }
        )
        self.assertEqual(order.warehouse_id, self.warehouse_2)
