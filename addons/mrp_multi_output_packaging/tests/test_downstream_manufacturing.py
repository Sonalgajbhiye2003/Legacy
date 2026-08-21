from unittest.mock import patch

from psycopg2 import IntegrityError
from psycopg2.errors import UniqueViolation

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import MultiOutputCommon


@tagged("post_install", "-at_install")
class TestDownstreamManufacturing(MultiOutputCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_litre = cls.env.ref("uom.product_uom_litre")
        cls.uom_millilitre = cls.env["uom.uom"].create({
            "name": "Test mL",
            "category_id": cls.uom_litre.category_id.id,
            "uom_type": "smaller",
            "factor": 1000.0,
            "rounding": 1.0,
        })
        cls.crude_oil = cls.env["product.product"].create({
            "name": "Test Crude Soya Oil",
            "type": "product",
            "tracking": "lot",
            "uom_id": cls.uom_litre.id,
            "uom_po_id": cls.uom_litre.id,
        })
        cls.refined_oil = cls.env["product.product"].create({
            "name": "Test Refined Soyabean Oil",
            "type": "product",
            "uom_id": cls.uom_litre.id,
            "uom_po_id": cls.uom_litre.id,
            "company_id": cls.company.id,
        })
        cls.workcenter = cls.env["mrp.workcenter"].create({
            "name": "Test Oil Refining Work Center",
            "company_id": cls.company.id,
        })
        cls.downstream_bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.refined_oil.product_tmpl_id.id,
            "product_id": cls.refined_oil.id,
            "product_qty": 10.0,
            "product_uom_id": cls.uom_litre.id,
            "type": "normal",
            "company_id": cls.company.id,
            "bom_line_ids": [
                Command.create({
                    "product_id": cls.crude_oil.id,
                    "product_qty": 2.0,
                    "product_uom_id": cls.uom_litre.id,
                }),
                Command.create({
                    "product_id": cls.pouch.id,
                    "product_qty": 1.0,
                    "product_uom_id": cls.uom_unit.id,
                }),
            ],
            "operation_ids": [Command.create({
                "name": "Refine and Pack Oil",
                "workcenter_id": cls.workcenter.id,
                "time_cycle_manual": 30.0,
            })],
        })
        cls.upstream_byproduct = cls.env["mrp.bom.byproduct"].create({
            "bom_id": cls.bom.id,
            "product_id": cls.crude_oil.id,
            "product_qty": 5000.0,
            "product_uom_id": cls.uom_millilitre.id,
            "cost_share": 20.0,
        })
        cls.bom.default_packaged_product_id = cls.pack_500

    def _configure_downstream(self):
        self.upstream_byproduct.write({
            "enable_downstream_manufacturing": True,
            "downstream_bom_id": self.downstream_bom.id,
        })

    def _create_upstream_byproduct_move(self):
        upstream = self.create_custom_mo(planned=1000.0)
        upstream.action_confirm()
        byproduct_move = upstream.move_byproduct_ids.filtered(
            lambda move: move.byproduct_id == self.upstream_byproduct
        )
        self.assertEqual(len(byproduct_move), 1)
        return upstream, byproduct_move

    def test_disabled_byproduct_keeps_standard_behavior(self):
        upstream, byproduct_move = self._create_upstream_byproduct_move()

        self.assertEqual(upstream.state, "confirmed")
        self.assertAlmostEqual(byproduct_move.product_uom_qty, 5000.0)
        self.assertEqual(byproduct_move.product_uom, self.uom_millilitre)
        self.assertFalse(byproduct_move.downstream_manufacturing_enabled)
        self.assertFalse(byproduct_move.downstream_production_id)
        with self.assertRaisesRegex(UserError, "not enabled"):
            byproduct_move.action_create_or_open_downstream_mo()

    def test_create_downstream_mo_uses_ratio_uom_and_standard_bom(self):
        self._configure_downstream()
        upstream, byproduct_move = self._create_upstream_byproduct_move()

        action = byproduct_move.action_create_or_open_downstream_mo()
        downstream = self.env["mrp.production"].browse(action["res_id"])

        self.assertEqual(downstream.source_byproduct_move_id, byproduct_move)
        self.assertEqual(downstream.source_manufacturing_order_id, upstream)
        self.assertEqual(downstream.product_id, self.refined_oil)
        self.assertEqual(downstream.bom_id, self.downstream_bom)
        self.assertEqual(downstream.product_uom_id, self.uom_litre)
        self.assertAlmostEqual(downstream.product_qty, 25.0)
        self.assertEqual(downstream.state, "draft")
        self.assertIn(upstream.name, downstream.origin)
        self.assertEqual(
            set(downstream.move_raw_ids.product_id.ids),
            {self.crude_oil.id, self.pouch.id},
        )
        self.assertEqual(len(downstream.workorder_ids), 1)

        downstream.action_confirm()
        self.assertEqual(downstream.state, "confirmed")
        self.assertEqual(len(downstream.workorder_ids), 1)
        self.assertEqual(
            downstream.workorder_ids.operation_id,
            self.downstream_bom.operation_ids,
        )
        crude_component_move = downstream.move_raw_ids.filtered(
            lambda move: move.product_id == self.crude_oil
        )
        self.assertEqual(crude_component_move.product_id.tracking, "lot")
        self.assertFalse(crude_component_move.move_line_ids)
        self.assertNotEqual(crude_component_move.state, "done")
        source_action = downstream.action_open_source_manufacturing_order()
        self.assertEqual(source_action["res_id"], upstream.id)

    def test_repeated_action_opens_same_mo_even_when_cancelled(self):
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()
        first_action = byproduct_move.action_create_or_open_downstream_mo()
        first = self.env["mrp.production"].browse(first_action["res_id"])

        second_action = byproduct_move.action_create_or_open_downstream_mo()
        self.assertEqual(second_action["res_id"], first.id)
        self.assertEqual(
            self.env["mrp.production"].search_count([
                ("source_byproduct_move_id", "=", byproduct_move.id)
            ]),
            1,
        )

        first.action_cancel()
        cancelled_action = byproduct_move.action_create_or_open_downstream_mo()
        self.assertEqual(cancelled_action["res_id"], first.id)
        self.assertEqual(first.state, "cancel")

    def test_actual_quantity_takes_precedence_over_plan(self):
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()
        byproduct_move.quantity = 4000.0

        action = byproduct_move.action_create_or_open_downstream_mo()
        downstream = self.env["mrp.production"].browse(action["res_id"])

        self.assertAlmostEqual(downstream.product_qty, 20.0)

    def test_custom_multi_output_downstream_bom_initializes_bulk_plan(self):
        self.downstream_bom.write({
            "manufacturing_workflow": "custom_multi_output",
            "custom_process_type": "integrated_production_packaging",
        })
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()

        action = byproduct_move.action_create_or_open_downstream_mo()
        downstream = self.env["mrp.production"].browse(action["res_id"])

        self.assertEqual(downstream.manufacturing_workflow, "custom_multi_output")
        self.assertEqual(
            downstream.custom_process_type, "integrated_production_packaging"
        )
        self.assertEqual(downstream.bulk_product_id, self.refined_oil)
        self.assertEqual(downstream.bulk_uom_id, self.uom_litre)
        self.assertAlmostEqual(downstream.planned_usable_output_qty, 25.0)

    def test_invalid_downstream_configuration_is_rejected(self):
        invalid_product = self.env["product.product"].create({
            "name": "Test Invalid Oil Output",
            "type": "product",
            "uom_id": self.uom_litre.id,
            "uom_po_id": self.uom_litre.id,
            "company_id": self.company.id,
        })
        invalid_bom = self.env["mrp.bom"].create({
            "product_tmpl_id": invalid_product.product_tmpl_id.id,
            "product_id": invalid_product.id,
            "product_qty": 1.0,
            "product_uom_id": self.uom_litre.id,
            "type": "normal",
            "company_id": self.company.id,
            "bom_line_ids": [Command.create({
                "product_id": self.pouch.id,
                "product_qty": 1.0,
                "product_uom_id": self.uom_unit.id,
            })],
        })
        with self.assertRaisesRegex(ValidationError, "does not contain"):
            self.upstream_byproduct.write({
                "enable_downstream_manufacturing": True,
                "downstream_bom_id": invalid_bom.id,
            })

    def test_database_constraint_prevents_duplicate_source_link(self):
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()
        action = byproduct_move.action_create_or_open_downstream_mo()
        existing = self.env["mrp.production"].browse(action["res_id"])

        with self.assertRaises(IntegrityError):
            existing.copy({"source_byproduct_move_id": byproduct_move.id})

    def test_concurrent_collision_returns_actionable_error(self):
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()

        with patch.object(
            type(self.env["mrp.production"]),
            "create",
            side_effect=UniqueViolation(),
        ), self.assertRaisesRegex(UserError, "Another request has already created"):
            byproduct_move.action_create_or_open_downstream_mo()

    def test_action_respects_manufacturing_access(self):
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()
        restricted_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Downstream Restricted User",
            "login": "downstream_restricted_user",
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([self.env.ref("base.group_user").id])],
        })

        with self.assertRaises(AccessError):
            byproduct_move.with_user(restricted_user).action_create_or_open_downstream_mo()

    def test_multi_output_user_can_create_downstream_mo(self):
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()
        manufacturing_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Downstream Manufacturing User",
            "login": "downstream_manufacturing_user",
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([
                self.env.ref("mrp_multi_output_packaging.group_multi_output_user").id
            ])],
        })

        action = byproduct_move.with_user(
            manufacturing_user
        ).action_create_or_open_downstream_mo()
        downstream = self.env["mrp.production"].browse(action["res_id"])

        self.assertEqual(downstream.create_uid, manufacturing_user)
        self.assertEqual(downstream.source_byproduct_move_id, byproduct_move)

    def test_manufacturing_manager_can_create_custom_downstream_mo(self):
        self.downstream_bom.write({
            "manufacturing_workflow": "custom_multi_output",
            "custom_process_type": "integrated_production_packaging",
        })
        self._configure_downstream()
        _upstream, byproduct_move = self._create_upstream_byproduct_move()
        manager = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Downstream Manufacturing Manager",
            "login": "downstream_manufacturing_manager",
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([self.env.ref("mrp.group_mrp_manager").id])],
        })

        action = byproduct_move.with_user(
            manager
        ).action_create_or_open_downstream_mo()
        downstream = self.env["mrp.production"].browse(action["res_id"])

        self.assertTrue(manager.has_group(
            "mrp_multi_output_packaging.group_multi_output_user"
        ))
        self.assertEqual(downstream.create_uid, manager)

    def test_cross_company_downstream_bom_is_rejected(self):
        other_company_values = {"name": "Downstream Other Company"}
        if "sequence_prefix" in self.env["res.company"]._fields:
            other_company_values["sequence_prefix"] = "DOC"
        other_company = self.env["res.company"].create(other_company_values)
        other_product = self.env["product.product"].create({
            "name": "Other Company Refined Oil",
            "type": "product",
            "uom_id": self.uom_litre.id,
            "uom_po_id": self.uom_litre.id,
            "company_id": other_company.id,
        })
        other_bom = self.env["mrp.bom"].create({
            "product_tmpl_id": other_product.product_tmpl_id.id,
            "product_id": other_product.id,
            "product_qty": 1.0,
            "product_uom_id": self.uom_litre.id,
            "type": "normal",
            "company_id": other_company.id,
            "bom_line_ids": [Command.create({
                "product_id": self.crude_oil.id,
                "product_qty": 1.0,
                "product_uom_id": self.uom_litre.id,
            })],
        })

        with self.assertRaises(UserError):
            self.upstream_byproduct.write({
                "enable_downstream_manufacturing": True,
                "downstream_bom_id": other_bom.id,
            })
