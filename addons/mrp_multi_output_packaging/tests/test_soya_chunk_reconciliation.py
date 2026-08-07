from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MultiOutputCommon


@tagged("post_install", "-at_install")
class TestSoyaChunkReconciliation(MultiOutputCommon):

    def test_planned_soya_chunk_balance(self):
        mo = self.create_custom_mo(planned=1000)
        self.add_output(mo, self.pack_100, self.recipe_100, 2000)
        self.add_output(mo, self.pack_500, self.recipe_500, 1000)
        self.add_output(mo, self.pack_1000, self.recipe_1000, 100)
        mo._sync_primary_bulk_output_line()
        self.assertAlmostEqual(mo.total_planned_packaged_equivalent, 800)
        self.assertAlmostEqual(mo.expected_remaining_bulk_qty, 200)
        bulk_line = mo.output_line_ids.filtered(lambda line: line.output_classification == "primary_bulk")
        self.assertEqual(len(bulk_line), 1)
        self.assertAlmostEqual(bulk_line.planned_qty, 200)
        self.assertNotIn(self.pack_100, mo.bom_id.byproduct_ids.product_id)

    def test_negative_remaining_blocks_completion(self):
        mo = self.create_custom_mo(planned=1000, actual=100)
        self.add_output(mo, self.pack_500, self.recipe_500, 1000, 1000)
        mo.action_confirm()
        with self.assertRaisesRegex(UserError, "Remaining Bulk"):
            mo._validate_custom_output_plan(completion=True)

    def test_packaging_variance_does_not_require_reason(self):
        mo = self.create_custom_mo(planned=1000, actual=1000)
        self.add_output(mo, self.pack_500, self.recipe_500, 1000, 1000)
        mo.action_confirm()
        for packaging_line in mo.packaging_line_ids:
            packaging_line.actual_consumed_qty = packaging_line.expected_actual_packaging_qty
        line = mo.packaging_line_ids.filtered(lambda item: item.packaging_product_id == self.pouch)
        line.actual_consumed_qty = line.expected_actual_packaging_qty - 10

        mo._validate_custom_output_plan(completion=True)
