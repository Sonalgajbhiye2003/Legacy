from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_purchase_approval")
class TestLegacyPurchaseApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.po_double_validation = "one_step"
        cls.purchase_user_group = cls.env.ref("purchase.group_purchase_user")
        cls.purchase_manager_group = cls.env.ref("purchase.group_purchase_manager")
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Approval Test Vendor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Approval Test Product",
                "type": "product",
                "purchase_ok": True,
                "uom_id": cls.uom_unit.id,
                "uom_po_id": cls.uom_unit.id,
                "company_id": False,
            }
        )
        cls.requester = cls._create_user("approval.requester", "PO Requester")
        cls.approver_1 = cls._create_user("approval.level1", "Level 1 Approver")
        cls.approver_2 = cls._create_user("approval.level2", "Level 2 Approver")
        cls.approver_3 = cls._create_user("approval.level3", "Level 3 Approver")
        cls.unauthorized = cls._create_user(
            "approval.unauthorized", "Unauthorized User"
        )
        cls.purchase_manager = cls._create_user(
            "approval.manager",
            "Purchase Manager",
            groups=cls.purchase_manager_group,
        )

    @classmethod
    def _create_user(cls, login, name, company=None, groups=None, companies=None):
        company = company or cls.company
        groups = groups or cls.purchase_user_group
        companies = companies or company
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": name,
                "login": login,
                "email": f"{login}@example.com",
                "company_id": company.id,
                "company_ids": [Command.set(companies.ids)],
                "groups_id": [Command.set(groups.ids)],
            }
        )

    def setUp(self):
        super().setUp()
        self.env["legacy.purchase.approval.config"].search([]).write(
            {"active": False}
        )

    def _create_config(
        self,
        level_2=False,
        level_3=False,
        company=None,
        approver_1=None,
        approver_2=None,
        approver_3=None,
        **extra,
    ):
        company = company or self.company
        values = {
            "name": extra.pop("name", "Approval Test Configuration"),
            "company_id": company.id,
            "currency_id": company.currency_id.id,
            "level_1_approver_id": (approver_1 or self.approver_1).id,
            "level_2_approver_id": (
                (approver_2 or self.approver_2).id if level_2 else False
            ),
            "level_3_approver_id": (
                (approver_3 or self.approver_3).id if level_3 else False
            ),
            "apply_to_all_purchase_orders": True,
        }
        values.update(extra)
        return self.env["legacy.purchase.approval.config"].create(values)

    def _create_purchase_order(
        self, price=100.0, company=None, requester=None, quantity=1.0
    ):
        company = company or self.company
        requester = requester or self.requester
        return self.env["purchase.order"].with_user(requester).create(
            {
                "partner_id": self.vendor.id,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.display_name,
                            "product_qty": quantity,
                            "product_uom": self.product.uom_po_id.id,
                            "price_unit": price,
                            "date_planned": fields.Datetime.now(),
                        }
                    )
                ],
            }
        )

    def _request_approval(self, order, requester=None):
        order.with_user(requester or self.requester).action_request_approval()
        return order

    def _approve_as(self, order, approver):
        order.with_user(approver).action_approve_purchase()
        return order

    def _reject_as(self, order, approver, reason):
        wizard = (
            self.env["legacy.purchase.rejection.wizard"]
            .with_user(approver)
            .create(
                {
                    "purchase_order_id": order.id,
                    "rejection_reason": reason,
                }
            )
        )
        wizard.action_confirm_rejection()
        return order

    def _mail(self, subject):
        return self.env["mail.mail"].search(
            [("subject", "=", subject)], order="id desc", limit=1
        )

    def _chatter_text(self, order):
        return "\n".join(str(body) for body in order.message_ids.mapped("body"))

    def _assert_confirmation_blocked(self, order, message):
        with self.assertRaisesRegex(UserError, message):
            order.with_user(self.requester).button_confirm()

    def test_configuration_with_level_one_can_be_created(self):
        config = self._create_config()

        self.assertTrue(config.active)
        self.assertEqual(config.level_1_approver_id, self.approver_1)
        self.assertFalse(config.level_2_approver_id)
        self.assertFalse(config.level_3_approver_id)

    def test_level_one_approver_is_mandatory(self):
        with self.assertRaises(IntegrityError):
            self.env["legacy.purchase.approval.config"].create(
                {
                    "name": "Invalid configuration",
                    "company_id": self.company.id,
                    "currency_id": self.company.currency_id.id,
                }
            )

    def test_level_three_requires_level_two(self):
        with self.assertRaisesRegex(ValidationError, "Level 2 approver"):
            self._create_config(level_3=True)

    def test_duplicate_approvers_and_invalid_amount_range_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "same user"):
            self._create_config(
                level_2=True,
                level_2_approver_id=self.approver_1.id,
            )
        with self.assertRaisesRegex(ValidationError, "Maximum Amount"):
            self._create_config(
                apply_to_all_purchase_orders=False,
                min_amount=100.0,
                max_amount=50.0,
            )

    def test_one_level_approval_flow(self):
        config = self._create_config()
        order = self._create_purchase_order()

        self._request_approval(order)

        self.assertTrue(order.approval_required)
        self.assertEqual(order.approval_config_id, config)
        self.assertEqual(order.approval_state, "waiting_level_1")
        self.assertEqual(order.current_approval_level, 1)
        self.assertEqual(order.level_1_approver_id, self.approver_1)
        self.assertEqual(order.approval_requested_by, self.requester)
        self.assertTrue(order.approval_requested_date)

        self._approve_as(order, self.approver_1)

        self.assertEqual(order.approval_state, "approved")
        self.assertEqual(order.level_1_approved_by, self.approver_1)
        self.assertTrue(order.level_1_approved_date)
        self.assertIn("Purchase approval completed", self._chatter_text(order))
        self.assertIn("Approval result email queued", self._chatter_text(order))
        order.with_user(self.requester).button_confirm()
        self.assertEqual(order.state, "purchase")

    def test_two_level_approval_flow(self):
        self._create_config(level_2=True)
        order = self._create_purchase_order()
        self._request_approval(order)

        self._approve_as(order, self.approver_1)

        self.assertEqual(order.approval_state, "waiting_level_2")
        self.assertEqual(order.current_approval_level, 2)
        self.assertEqual(order.current_approver_id, self.approver_2)
        self.assertIn(
            f"Approval request email queued for {self.approver_2.display_name}",
            self._chatter_text(order),
        )

        self._approve_as(order, self.approver_2)

        self.assertEqual(order.approval_state, "approved")
        self.assertEqual(order.level_2_approved_by, self.approver_2)
        self.assertTrue(order.level_2_approved_date)
        self.assertIn("Approval result email queued", self._chatter_text(order))
        order.with_user(self.requester).button_confirm()
        self.assertEqual(order.state, "purchase")

    def test_three_level_approval_flow(self):
        self._create_config(level_2=True, level_3=True)
        order = self._create_purchase_order()
        self._request_approval(order)

        self._approve_as(order, self.approver_1)
        self.assertEqual(order.approval_state, "waiting_level_2")
        self._approve_as(order, self.approver_2)
        self.assertEqual(order.approval_state, "waiting_level_3")
        self._approve_as(order, self.approver_3)

        self.assertEqual(order.approval_state, "approved")
        self.assertEqual(order.level_1_approved_by, self.approver_1)
        self.assertEqual(order.level_2_approved_by, self.approver_2)
        self.assertEqual(order.level_3_approved_by, self.approver_3)
        self.assertTrue(order.level_3_approved_date)
        self.assertIn("Purchase approval completed", self._chatter_text(order))
        order.with_user(self.requester).button_confirm()
        self.assertEqual(order.state, "purchase")

    def test_rejection_at_level_one(self):
        self._create_config()
        order = self._create_purchase_order()
        self._request_approval(order)

        self._reject_as(order, self.approver_1, "Level 1 budget rejection")

        self.assertEqual(order.approval_state, "rejected")
        self.assertEqual(order.rejection_reason, "Level 1 budget rejection")
        self.assertEqual(order.rejected_by_id, self.approver_1)
        self.assertIn("Level 1 budget rejection", self._chatter_text(order))
        self.assertIn("Approval result email queued", self._chatter_text(order))
        self._assert_confirmation_blocked(order, "has been rejected")

    def test_rejection_at_level_two(self):
        self._create_config(level_2=True)
        order = self._create_purchase_order()
        self._request_approval(order)
        self._approve_as(order, self.approver_1)

        self._reject_as(order, self.approver_2, "Level 2 commercial rejection")

        self.assertEqual(order.approval_state, "rejected")
        self.assertEqual(order.rejection_reason, "Level 2 commercial rejection")
        self.assertEqual(order.rejected_by_id, self.approver_2)
        self._assert_confirmation_blocked(order, "has been rejected")

    def test_rejection_at_level_three(self):
        self._create_config(level_2=True, level_3=True)
        order = self._create_purchase_order()
        self._request_approval(order)
        self._approve_as(order, self.approver_1)
        self._approve_as(order, self.approver_2)

        self._reject_as(order, self.approver_3, "Level 3 executive rejection")

        self.assertEqual(order.approval_state, "rejected")
        self.assertEqual(order.rejection_reason, "Level 3 executive rejection")
        self.assertEqual(order.rejected_by_id, self.approver_3)
        self._assert_confirmation_blocked(order, "has been rejected")

    def test_rejection_reason_is_mandatory(self):
        self._create_config()
        order = self._create_purchase_order()
        self._request_approval(order)

        with self.assertRaisesRegex(UserError, "rejection reason"):
            order.with_user(self.approver_1)._apply_rejection("  ")

    def test_unauthorized_user_cannot_approve_or_reject(self):
        self._create_config()
        order = self._create_purchase_order()
        self._request_approval(order)

        self.assertFalse(order.with_user(self.unauthorized).can_current_user_approve)
        with self.assertRaisesRegex(AccessError, "configured approver"):
            order.with_user(self.unauthorized).action_approve_purchase()
        with self.assertRaisesRegex(AccessError, "configured approver"):
            order.with_user(self.unauthorized).action_open_rejection_wizard()
        with self.assertRaisesRegex(AccessError, "configured approver"):
            order.with_user(self.unauthorized)._apply_rejection("Not allowed")

    def test_approval_fields_cannot_be_modified_directly(self):
        self._create_config()
        order = self._create_purchase_order()
        self._request_approval(order)

        with self.assertRaisesRegex(AccessError, "approval fields"):
            order.with_user(self.requester).write({"approval_state": "approved"})

    def test_confirmation_is_blocked_while_approval_is_pending(self):
        self._create_config(level_2=True)
        order = self._create_purchase_order()
        self._request_approval(order)

        self._assert_confirmation_blocked(order, "approval is still pending")
        self._approve_as(order, self.approver_1)
        self._assert_confirmation_blocked(order, "approval is still pending")

    def test_no_configuration_has_clear_error(self):
        order = self._create_purchase_order()

        with self.assertRaisesRegex(
            UserError, "No purchase approval configuration found for this purchase order"
        ):
            self._request_approval(order)

    def test_amount_based_configuration_selection(self):
        first = self._create_config(
            name="Low value",
            sequence=5,
            apply_to_all_purchase_orders=False,
            min_amount=0.0,
            max_amount=99.99,
        )
        second = self._create_config(
            name="High value",
            sequence=10,
            apply_to_all_purchase_orders=False,
            min_amount=100.0,
            max_amount=500.0,
            approver_1=self.approver_2,
        )
        order = self._create_purchase_order(price=250.0)

        self._request_approval(order)

        self.assertNotEqual(order.approval_config_id, first)
        self.assertEqual(order.approval_config_id, second)
        self.assertEqual(order.level_1_approver_id, self.approver_2)

    def test_company_specific_configuration_selection(self):
        company_b = self.env["res.company"].create(
            {
                "name": "Approval Test Company B",
                "currency_id": self.company.currency_id.id,
                "sequence_prefix": "APB",
            }
        )
        requester_b = self._create_user(
            "approval.requester.b", "Company B Requester", company=company_b
        )
        approver_b = self._create_user(
            "approval.level1.b", "Company B Approver", company=company_b
        )
        config_a = self._create_config(name="Company A Approval")
        config_b = self._create_config(
            name="Company B Approval",
            company=company_b,
            approver_1=approver_b,
        )
        order_a = self._create_purchase_order()
        order_b = self._create_purchase_order(company=company_b, requester=requester_b)

        self._request_approval(order_a)
        self._request_approval(order_b, requester=requester_b)

        self.assertEqual(order_a.approval_config_id, config_a)
        self.assertEqual(order_a.level_1_approver_id, self.approver_1)
        self.assertEqual(order_b.approval_config_id, config_b)
        self.assertEqual(order_b.level_1_approver_id, approver_b)
        self.assertNotEqual(order_a.level_1_approver_id, order_b.level_1_approver_id)

    def test_reset_rejected_approval_and_resubmit(self):
        self._create_config()
        order = self._create_purchase_order()
        self._request_approval(order)
        self._reject_as(order, self.approver_1, "Correct and resubmit")

        order.with_user(self.purchase_manager).action_reset_purchase_approval()

        self.assertEqual(order.approval_state, "draft")
        self.assertEqual(order.current_approval_level, 0)
        self.assertFalse(order.approval_required)
        self.assertFalse(order.rejection_reason)
        self.assertFalse(order.rejected_by_id)
        self._request_approval(order)
        self.assertEqual(order.approval_state, "waiting_level_1")

    def test_chatter_logs_each_approval_level_and_rejection_reason(self):
        self._create_config(level_2=True, level_3=True)
        approved_order = self._create_purchase_order()
        self._request_approval(approved_order)
        self._approve_as(approved_order, self.approver_1)
        self._approve_as(approved_order, self.approver_2)
        self._approve_as(approved_order, self.approver_3)
        chatter = self._chatter_text(approved_order)

        self.assertIn("Purchase approval requested", chatter)
        self.assertIn("Level 1 approved", chatter)
        self.assertIn("Level 2 approved", chatter)
        self.assertIn("Level 3 approved", chatter)
        self.assertIn("Purchase approval completed", chatter)

        rejected_order = self._create_purchase_order(price=200.0)
        self._request_approval(rejected_order)
        self._reject_as(rejected_order, self.approver_1, "Chatter rejection reason")
        rejected_chatter = self._chatter_text(rejected_order)
        self.assertIn("Purchase Order rejected at Level 1", rejected_chatter)
        self.assertIn("Chatter rejection reason", rejected_chatter)

    def test_email_records_for_request_approval_and_rejection(self):
        self._create_config()
        approved_order = self._create_purchase_order()
        self._request_approval(approved_order)

        request_mail = self._mail(
            f"Purchase Order Approval Required: {approved_order.name}"
        )
        self.assertTrue(request_mail)
        self.assertIn(self.approver_1.partner_id, request_mail.recipient_ids)

        self._approve_as(approved_order, self.approver_1)
        approval_mail = self._mail(f"Purchase Order Approved: {approved_order.name}")
        self.assertTrue(approval_mail)
        self.assertIn(self.requester.partner_id, approval_mail.recipient_ids)

        rejected_order = self._create_purchase_order(price=200.0)
        self._request_approval(rejected_order)
        self._reject_as(rejected_order, self.approver_1, "Email rejection")
        rejection_mail = self._mail(f"Purchase Order Rejected: {rejected_order.name}")
        self.assertTrue(rejection_mail)
        self.assertIn(self.requester.partner_id, rejection_mail.recipient_ids)
