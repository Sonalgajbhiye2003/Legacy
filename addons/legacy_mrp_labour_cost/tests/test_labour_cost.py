from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestManufacturingLabourCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.warehouse:
            raise AssertionError("The test company requires a warehouse.")
        cls.product = cls.env["product.product"].create(
            {"name": "Labour Cost Test Product", "type": "product"}
        )
        cls.workcenter = cls.env["mrp.workcenter"].create(
            {"name": "Labour Test Work Center", "company_id": cls.company.id}
        )
        cls.debit_account = cls.env["account.account"].create(
            {
                "name": "Manufacturing Labour Test Expense",
                "code": "LCTEXP",
                "account_type": "expense",
                "company_id": cls.company.id,
            }
        )
        cls.credit_account = cls.env["account.account"].create(
            {
                "name": "Manufacturing Labour Test Clearing",
                "code": "LCTCLR",
                "account_type": "liability_current",
                "company_id": cls.company.id,
            }
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Manufacturing Labour Test Journal",
                "code": "LCTJ",
                "type": "general",
                "company_id": cls.company.id,
            }
        )
        cls.company.write(
            {
                "manufacturing_labour_journal_id": cls.journal.id,
                "manufacturing_labour_debit_account_id": cls.debit_account.id,
                "manufacturing_labour_credit_account_id": cls.credit_account.id,
            }
        )
        cls.poster = cls._create_user(
            "labour_poster",
            ["mrp.group_mrp_manager", "account.group_account_user"],
        )
        cls.mrp_user = cls._create_user("labour_mrp_user", ["mrp.group_mrp_user"])
        cls.account_manager = cls._create_user(
            "labour_account_manager",
            [
                "mrp.group_mrp_manager",
                "account.group_account_manager",
            ],
        )

    @classmethod
    def _create_user(cls, login, group_xmlids):
        groups = [cls.env.ref(xmlid).id for xmlid in group_xmlids]
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login.replace("_", " ").title(),
                "login": login,
                "email": f"{login}@example.invalid",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "groups_id": [Command.set(groups)],
            }
        )

    def _create_production(self, confirmed=True):
        production = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "product_qty": 10.0,
                "product_uom_id": self.product.uom_id.id,
                "picking_type_id": self.warehouse.manu_type_id.id,
                "location_src_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "company_id": self.company.id,
            }
        )
        if confirmed:
            production.action_confirm()
            self.assertNotEqual(production.state, "draft")
        return production

    def _create_line(
        self,
        production,
        labour_count=3,
        hours=4.0,
        rate=150.0,
        description="Production Operators",
    ):
        return self.env["mrp.production.labour.cost"].create(
            {
                "production_id": production.id,
                "workcenter_id": self.workcenter.id,
                "labour_type": "production",
                "description": description,
                "labour_count": labour_count,
                "hours_per_labour": hours,
                "cost_per_hour": rate,
            }
        )

    def _post(self, production):
        production.with_user(self.poster).action_post_labour_cost()
        return production.labour_account_move_ids.filtered(
            lambda move: not move.reversed_entry_id
        ).sorted("id")[-1]

    def _create_labour_preset_bom(self, suffix="A", rate=100.0):
        preset = self.env["mrp.labour.cost.preset"].create(
            {
                "name": f"TSP Crew {suffix}",
                "company_id": self.company.id,
                "workcenter_id": self.workcenter.id,
                "labour_type": "production",
                "description": f"Preset Crew {suffix}",
                "labour_count": 4,
                "hours_per_labour": 8.0,
                "cost_per_hour": rate,
            }
        )
        bom = self.env["mrp.bom"].create(
            {
                "code": f"LABOUR-PRESET-{suffix}",
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "product_id": self.product.id,
                "product_qty": 1.0,
                "product_uom_id": self.product.uom_id.id,
                "type": "normal",
                "company_id": self.company.id,
                "labour_preset_line_ids": [
                    Command.create({"labour_preset_id": preset.id})
                ],
            }
        )
        return preset, bom, bom.labour_preset_line_ids

    def test_01_calculation_and_mo_totals(self):
        production = self._create_production()
        line = self._create_line(production)
        self.assertEqual(line.total_hours, 12.0)
        self.assertEqual(line.total_cost, 1800.0)
        second = self._create_line(
            production, labour_count=2, hours=3.5, rate=250.0, description="Packaging"
        )
        self.assertEqual(second.total_cost, 1750.0)
        self.assertEqual(production.labour_line_count, 2)
        self.assertEqual(production.labour_total_headcount, 5)
        self.assertEqual(production.labour_total_hours, 19.0)
        self.assertEqual(production.labour_total_cost, 3550.0)
        self.assertEqual(production.labour_unposted_cost, 3550.0)

    def test_02_multiple_entries_same_workcenter(self):
        production = self._create_production()
        for description, count, hours, rate in [
            ("Filling", 3, 4, 120),
            ("Sealing", 2, 3, 130),
            ("Labelling", 2, 3, 125),
        ]:
            self._create_line(production, count, hours, rate, description)
        self.assertEqual(production.labour_line_count, 3)
        self.assertEqual(len(production.labour_cost_line_ids.workcenter_id), 1)
        self.assertEqual(production.labour_total_cost, 2970.0)

    def test_03_validation(self):
        production = self._create_production()
        with self.assertRaises(ValidationError):
            self._create_line(production, labour_count=0)
        with self.assertRaises(ValidationError):
            self._create_line(production, hours=-1)
        with self.assertRaises(ValidationError):
            self._create_line(production, rate=-1)

        other_company_values = {
            "name": "Labour Other Company",
        }
        # This legacy database has an independent company-prefix customization.
        if "sequence_prefix" in self.env["res.company"]._fields:
            other_company_values["sequence_prefix"] = "LCO"
        other_company = self.env["res.company"].create(other_company_values)
        other_workcenter = self.env["mrp.workcenter"].create(
            {"name": "Other Company Work Center", "company_id": other_company.id}
        )
        with self.assertRaises(ValidationError):
            self.env["mrp.production.labour.cost"].create(
                {
                    "production_id": production.id,
                    "workcenter_id": other_workcenter.id,
                    "labour_count": 1,
                    "hours_per_labour": 1,
                    "cost_per_hour": 1,
                }
            )

    def test_04_posting_balance_reference_and_state(self):
        production = self._create_production()
        first = self._create_line(production, 3, 4, 150, "Mixing")
        second = self._create_line(production, 2, 3.5, 250, "Extrusion")
        third = self._create_line(production, 3, 5, 125, "Packaging")
        move = self._post(production)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.labour_production_id, production)
        self.assertIn(production.name, move.ref)
        self.assertEqual(sum(move.line_ids.mapped("debit")), 5425.0)
        self.assertEqual(sum(move.line_ids.mapped("credit")), 5425.0)
        self.assertEqual(len(move.line_ids.filtered(lambda line: line.debit)), 3)
        self.assertTrue(all(line.posting_state == "posted" for line in first | second | third))
        self.assertTrue(all(line.account_move_id == move for line in first | second | third))
        self.assertEqual(production.labour_posted_cost, 5425.0)
        self.assertEqual(production.labour_unposted_cost, 0.0)

    def test_05_duplicate_and_partial_posting(self):
        production = self._create_production()
        first = self._create_line(production, 3, 4, 150)
        first_move = self._post(production)
        with self.assertRaises(UserError):
            production.with_user(self.poster).action_post_labour_cost()
        self.assertEqual(first.account_move_id, first_move)

        second = self._create_line(production, 2, 3, 125, "Correction")
        second_move = self._post(production)
        self.assertNotEqual(first_move, second_move)
        self.assertEqual(first.account_move_id, first_move)
        self.assertEqual(second.account_move_id, second_move)
        self.assertEqual(sum(second_move.line_ids.mapped("debit")), 750.0)

    def test_06_missing_configuration_and_atomic_state(self):
        production = self._create_production()
        line = self._create_line(production)
        original = {
            "manufacturing_labour_journal_id": self.company.manufacturing_labour_journal_id.id,
            "manufacturing_labour_debit_account_id": self.company.manufacturing_labour_debit_account_id.id,
            "manufacturing_labour_credit_account_id": self.company.manufacturing_labour_credit_account_id.id,
        }
        fields_to_test = [
            "manufacturing_labour_journal_id",
            "manufacturing_labour_debit_account_id",
            "manufacturing_labour_credit_account_id",
        ]
        try:
            for field_name in fields_to_test:
                self.company.write({field_name: False})
                with self.assertRaises(UserError):
                    production.with_user(self.poster).action_post_labour_cost()
                self.assertEqual(line.posting_state, "draft")
                self.assertFalse(line.account_move_id)
                self.company.write({field_name: original[field_name]})
        finally:
            self.company.write(original)

    def test_07_security_and_posted_immutability(self):
        production = self._create_production()
        line = self._create_line(production)
        with self.assertRaises(AccessError):
            production.with_user(self.mrp_user).action_post_labour_cost()
        self._post(production)
        with self.assertRaises(AccessError):
            line.with_user(self.poster).write({"cost_per_hour": 200})
        with self.assertRaises(UserError):
            line.with_user(self.poster).unlink()

    def test_08_reversal(self):
        production = self._create_production()
        line = self._create_line(production)
        move = self._post(production)
        with self.assertRaises(AccessError):
            production.with_user(self.poster).action_open_labour_reversal_wizard()
        action = (
            self.env["mrp.labour.cost.reversal.wizard"]
            .with_user(self.account_manager)
            .create(
                {
                    "production_id": production.id,
                    "move_id": move.id,
                    "reason": "Test correction",
                }
            )
            .action_reverse_labour_cost()
        )
        reversal = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(reversal.state, "posted")
        self.assertEqual(reversal.reversed_entry_id, move)
        self.assertEqual(reversal.labour_production_id, production)
        self.assertEqual(line.posting_state, "reversed")
        self.assertEqual(line.reversal_move_id, reversal)
        self.assertEqual(production.labour_reversed_cost, line.total_cost)

    def test_09_zero_quantity_and_report_views(self):
        production = self._create_production()
        line = self._create_line(production)
        self.assertEqual(production.qty_produced, 0.0)
        self.assertEqual(line.labour_cost_per_unit, 0.0)
        action = self.env.ref("legacy_mrp_labour_cost.action_mrp_labour_cost_analysis")
        self.assertEqual(action.res_model, "mrp.production.labour.cost")
        views = self.env["mrp.production.labour.cost"].get_views(
            [
                (self.env.ref("legacy_mrp_labour_cost.mrp_labour_cost_tree").id, "tree"),
                (self.env.ref("legacy_mrp_labour_cost.mrp_labour_cost_pivot").id, "pivot"),
                (self.env.ref("legacy_mrp_labour_cost.mrp_labour_cost_graph").id, "graph"),
                (self.env.ref("legacy_mrp_labour_cost.mrp_labour_cost_search").id, "search"),
            ]
        )
        self.assertEqual(views["views"]["search"]["model"], "mrp.production.labour.cost")

    def test_10_draft_cancelled_and_locked_period(self):
        draft_production = self._create_production(confirmed=False)
        self._create_line(draft_production)
        with self.assertRaises(UserError):
            draft_production.with_user(self.poster).action_post_labour_cost()

        cancelled_production = self._create_production()
        self._create_line(cancelled_production)
        cancelled_production.action_cancel()
        self.assertEqual(cancelled_production.state, "cancel")
        with self.assertRaises(UserError):
            cancelled_production.with_user(self.poster).action_post_labour_cost()

        production = self._create_production()
        line = self._create_line(production)
        previous_lock = self.company.fiscalyear_lock_date
        try:
            self.company.fiscalyear_lock_date = fields.Date.context_today(self.company)
            move = self._post(production)
            self.assertGreater(move.date, self.company.fiscalyear_lock_date)
            self.assertEqual(line.posting_state, "posted")
            self.assertEqual(line.account_move_id, move)
            self.assertEqual(line.posting_date, move.date)
        finally:
            self.company.fiscalyear_lock_date = previous_lock

    def test_11_journal_posting_failure_is_atomic(self):
        production = self._create_production()
        line = self._create_line(production)
        move_count = self.env["account.move"].search_count(
            [("labour_production_id", "=", production.id)]
        )
        account_move_model = type(self.env["account.move"])
        with patch.object(
            account_move_model,
            "action_post",
            autospec=True,
            side_effect=UserError("Simulated journal posting failure"),
        ):
            with self.assertRaises(UserError):
                production.with_user(self.poster).action_post_labour_cost()
        self.assertEqual(line.posting_state, "draft")
        self.assertFalse(line.account_move_id)
        self.assertEqual(
            self.env["account.move"].search_count(
                [("labour_production_id", "=", production.id)]
            ),
            move_count,
        )

    def test_12_bom_preset_auto_load_and_refresh(self):
        preset, bom, bom_line = self._create_labour_preset_bom()
        production = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "product_qty": 10.0,
                "product_uom_id": self.product.uom_id.id,
                "bom_id": bom.id,
                "picking_type_id": self.warehouse.manu_type_id.id,
                "location_src_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "company_id": self.company.id,
            }
        )
        generated = production.labour_cost_line_ids.filtered("bom_labour_line_id")
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated.bom_labour_line_id, bom_line)
        self.assertEqual(generated.labour_preset_id, preset)
        self.assertEqual(generated.labour_count, 4)
        self.assertEqual(generated.hours_per_labour, 8.0)
        self.assertEqual(generated.cost_per_hour, 100.0)
        self.assertEqual(generated.total_cost, 3200.0)

        generated.write({"hours_per_labour": 2.0})
        production.action_load_labour_from_bom()
        self.assertEqual(len(production.labour_cost_line_ids.filtered("bom_labour_line_id")), 1)
        self.assertEqual(generated.hours_per_labour, 8.0)

    def test_13_bom_change_preserves_manual_lines_without_duplicates(self):
        _preset_a, bom_a, _line_a = self._create_labour_preset_bom("A2", 100.0)
        preset_b, bom_b, line_b = self._create_labour_preset_bom("B", 125.0)
        production = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "product_qty": 10.0,
                "product_uom_id": self.product.uom_id.id,
                "bom_id": bom_a.id,
                "picking_type_id": self.warehouse.manu_type_id.id,
                "location_src_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "company_id": self.company.id,
            }
        )
        manual = self._create_line(production, description="Manual adjustment")
        production.write({"bom_id": bom_b.id})
        self.assertTrue(manual.exists())
        generated = production.labour_cost_line_ids.filtered("bom_labour_line_id")
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated.bom_labour_line_id, line_b)
        self.assertEqual(generated.labour_preset_id, preset_b)
        self.assertEqual(generated.cost_per_hour, 125.0)
        production.action_load_labour_from_bom()
        self.assertEqual(len(production.labour_cost_line_ids), 2)
