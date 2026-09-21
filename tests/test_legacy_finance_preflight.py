"""Offline unit tests. These are NOT Odoo accounting integration tests."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "legacy_finance_preflight.py"
spec = importlib.util.spec_from_file_location("finance_preflight", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AmountTests(unittest.TestCase):
    def test_balanced_accounts_are_not_certified(self):
        r = audit.balance_summary([{"debit": 100.0}, {"credit": 100.0}], .01)
        self.assertTrue(r["balanced_within_half_currency_unit"])
        self.assertFalse(r["certifies_mapping_or_completeness"])

    def test_equal_omissions_cannot_be_certified(self):
        r = audit.balance_summary([], .01)
        self.assertTrue(r["balanced_within_half_currency_unit"])
        self.assertFalse(r["certifies_mapping_or_completeness"])

    def test_unbalanced(self):
        self.assertFalse(audit.balance_summary([{"debit": 100, "credit": 99}], .01)["balanced_within_half_currency_unit"])

    def test_half_currency_unit_is_not_ignored(self):
        self.assertFalse(audit.balance_summary([{"debit": ".005"}], .01)["balanced_within_half_currency_unit"])

    def test_decimal_sums(self):
        r = audit.balance_summary([{"debit": .1}, {"debit": .2}, {"credit": .3}], .01)
        self.assertEqual(r["difference"], "0.0")

    def test_contra_balances_preserve_sign(self):
        r = audit.balance_summary([{"debit": 500}, {"credit": 100}], .01)
        self.assertEqual(r["difference"], "400")

    def test_nonfinite_values_rejected(self):
        for value in ["NaN", "Infinity", "-Infinity", "bad"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.decimal_value(value)

    def test_invalid_rounding(self):
        for value in [0, -.01]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.balance_summary([], value)

    def test_duplicate_codes(self):
        self.assertEqual(audit.duplicate_account_codes([{"code":"A"},{"code":"B"},{"code":"A"}]), ["A"])


class PrivacyTests(unittest.TestCase):
    def test_local_json_written(self):
        with tempfile.TemporaryDirectory() as directory:
            p = audit.save_private_json({"status":"NOT_CERTIFIED"}, Path(directory) / "out.json")
            self.assertEqual(json.loads(p.read_text())["status"], "NOT_CERTIFIED")

    def test_existing_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "out.json"
            p.write_text("original")
            with self.assertRaises(FileExistsError):
                audit.save_private_json({}, p)
            self.assertEqual(p.read_text(), "original")

    def test_refuses_git_working_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            with self.assertRaises(RuntimeError):
                audit.save_private_json({}, root / "private" / "out.json")
            self.assertFalse((root / "private").exists())

    def test_refuses_git_worktree_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: elsewhere")
            with self.assertRaises(RuntimeError):
                audit.save_private_json({}, root / "out.json")


class TransactionTests(unittest.TestCase):
    def make_env(self):
        cursor = MagicMock()
        manager = MagicMock()
        manager.__enter__.return_value = cursor
        registry = MagicMock()
        registry.cursor.return_value = manager
        return SimpleNamespace(cr=SimpleNamespace(dbname=audit.EXPECTED_DATABASE),
                               registry=registry, uid=2, context={}), cursor

    def odoo_stub(self, major=17):
        return SimpleNamespace(api=SimpleNamespace(Environment=MagicMock(return_value="READONLY_ENV")),
                               release=SimpleNamespace(version_info=(major,0), version=f"{major}.0"))

    def test_database_mismatch_never_opens_cursor(self):
        env, cursor = self.make_env()
        env.cr.dbname = "production_other"
        with self.assertRaises(RuntimeError):
            audit.run_read_only(env, dt.date(2025,12,31))
        env.registry.cursor.assert_not_called()

    def test_missing_shell_environment(self):
        with self.assertRaises(RuntimeError):
            audit.run_read_only(None, dt.date(2025,12,31))

    def test_wrong_version_never_opens_cursor(self):
        env, cursor = self.make_env()
        with patch.dict(sys.modules,{"odoo":self.odoo_stub(18)}), self.assertRaises(RuntimeError):
            audit.run_read_only(env, dt.date(2025,12,31))
        env.registry.cursor.assert_not_called()

    def test_readonly_before_collection_and_rollback(self):
        env, cursor = self.make_env()
        def collect(*args):
            cursor.execute.assert_called_once_with("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            return {"status":"PREFLIGHT_ONLY"}
        with patch.dict(sys.modules,{"odoo":self.odoo_stub()}), patch.object(audit,"collect",side_effect=collect):
            r = audit.run_read_only(env, dt.date(2025,12,31))
        self.assertTrue(r["read_only_transaction"])
        cursor.rollback.assert_called_once()
        cursor.commit.assert_not_called()

    def test_failure_rolls_back_and_is_not_hidden(self):
        env, cursor = self.make_env()
        with patch.dict(sys.modules,{"odoo":self.odoo_stub()}), patch.object(audit,"collect",side_effect=ValueError("failed")):
            with self.assertRaisesRegex(ValueError,"failed"):
                audit.run_read_only(env, dt.date(2025,12,31))
        cursor.rollback.assert_called_once()
        cursor.commit.assert_not_called()

    def test_date_validation(self):
        with self.assertRaises(ValueError):
            audit.collect(None,"2025-12-31")

    def test_limit_validation(self):
        with self.assertRaises(ValueError):
            audit.collect(None,dt.date(2025,12,31),sample_limit=0)

    def test_all_requested_workflows_declared(self):
        expected={"sales","purchase","manufacturing","write_off","internal_transfer","material_requisition","repairs","quality","expenses","capex_opex","period_close"}
        self.assertEqual(set(audit.WORKFLOWS),expected)


if __name__ == "__main__":
    unittest.main()
