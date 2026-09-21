"""Read-only Odoo 17 financial preflight; execute inside the local Odoo shell.

Not a posting engine, installer, or production certification. Output contains
financial data: keep it outside the repository. No credentials are read/exported.
"""
from __future__ import annotations

import datetime as dt
import inspect
import json
import os
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED_DATABASE = "odoo17_legacy_masterdata_dev"
CORE_MODULES = (
    "account", "account_reports", "stock", "stock_account", "sale_stock",
    "purchase_stock", "mrp", "mrp_account", "repair", "maintenance",
    "hr_expense", "account_asset", "quality_control", "quality_mrp",
    "stock_landed_costs", "mrp_multi_output_packaging", "legacy_mrp_master_data",
)
P_AND_L_TYPES = ("income", "income_other", "expense", "expense_depreciation", "expense_direct_cost")
WORKFLOWS = {
    "sales": "Invoice/credit note, receipt/reconciliation and valuation/COGS timing must reconcile; order confirmation alone is not revenue.",
    "purchase": "Receipt, bill, price differences, landed cost and vendor return must reconcile without treating stock purchases twice as expense.",
    "manufacturing": "Raw material, packaging, WIP, each output/by-product and loss must have the approved quantity and cost treatment.",
    "write_off": "Scrap/inventory adjustment or receivable write-off posts once to approved accounts; reversals remain traceable.",
    "internal_transfer": "An owned internal-to-internal movement within one company ordinarily has no P&L effect. Do not invent an expense entry.",
    "material_requisition": "Approval is not consumption. Exactly one stock/accounting owner handles actual issues, partial issues and returns.",
    "repairs": "Actual parts and approved labour/services follow OPEX or qualifying CAPEX policy once, not both requisition and repair posting.",
    "quality": "A quality check/hold alone is not a loss. Subsequent scrap, impairment, rework or return determines the accounting event.",
    "expenses": "Posted expenses, payable/reimbursement and payment clear correctly; approval and payment must not duplicate expense.",
    "capex_opex": "Qualifying costs accumulate in capital CWIP then transfer once to PPE; available-for-use, payroll recovery and depreciation must reconcile.",
    "period_close": "Opening balances, prior/current earnings, allocation, accruals, tax, FX and reversals must be complete at the chosen accounting date.",
}


def decimal_value(value):
    """Keep numeric checks decimal-based; refuse non-finite/invalid amounts."""
    try:
        result = Decimal(str(value or 0))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid numeric value") from exc
    if not result.is_finite():
        raise ValueError("Non-finite numeric value")
    return result


def balance_summary(rows, rounding):
    """A balanced trial balance is a necessary check, not report certification."""
    debit = sum((decimal_value(row.get("debit")) for row in rows), Decimal(0))
    credit = sum((decimal_value(row.get("credit")) for row in rows), Decimal(0))
    delta = debit - credit
    unit = decimal_value(rounding)
    if unit <= 0:
        raise ValueError("Currency rounding must be positive")
    return {
        "debit": str(debit), "credit": str(credit), "difference": str(delta),
        "balanced_within_half_currency_unit": abs(delta) < unit / 2,
        "certifies_mapping_or_completeness": False,
    }


def duplicate_account_codes(accounts):
    counts = Counter(row["code"] for row in accounts)
    return sorted(code for code, count in counts.items() if count > 1)


def installed_model(env, name):
    return name in env.registry.models


def stored_fields(model, names):
    return [name for name in names if name in model._fields and model._fields[name].store]


def records(model, domain, names, limit=None):
    """Return only explicit stored fields; never export message/partner content."""
    selected = stored_fields(model, names)
    return model.search_read(domain, selected, limit=limit, order="id")


def monetary_groups(model, domain, grouping):
    return model.read_group(domain, grouping + ["debit:sum", "credit:sum", "balance:sum"], grouping, lazy=False)


def method_origins(env, model_name, method_names):
    """Identify the actual override chain without invoking posting methods."""
    if not installed_model(env, model_name):
        return {"available": False}
    result = {}
    for name in method_names:
        entries = []
        for cls in type(env[model_name]).__mro__:
            method = cls.__dict__.get(name)
            if method is None:
                continue
            try:
                entries.append({"module": cls.__module__, "signature": str(inspect.signature(method)),
                                "source": inspect.getsourcefile(method)})
            except (TypeError, ValueError, OSError):
                entries.append({"module": cls.__module__, "signature": "unavailable"})
        result[name] = entries
    return result


def company_snapshot(env, company, report_date, sample_limit):
    context = dict(env.context, allowed_company_ids=[company.id], active_test=False)
    local = env(context=context)
    aml = local["account.move.line"].with_company(company)
    company_domain = [("company_id", "=", company.id)]
    posted = company_domain + [("parent_state", "=", "posted"), ("date", "<=", report_date)]
    accounts = records(local["account.account"], company_domain,
        ["code", "name", "account_type", "company_id", "deprecated", "reconcile", "currency_id"])
    closing = monetary_groups(aml, posted, ["account_id"])
    fy = company.compute_fiscalyear_dates(report_date) if hasattr(company, "compute_fiscalyear_dates") else None
    period_domain = posted + ([("date", ">=", fy["date_from"])] if fy else [])
    pnl = None if fy is None else monetary_groups(aml, period_domain + [
        ("account_id.account_type", "in", list(P_AND_L_TYPES))], ["account_id"])
    revenue_no_product = None if fy is None else monetary_groups(aml, period_domain + [
        ("account_id.account_type", "in", ["income", "income_other"]), ("product_id", "=", False)], ["account_id"])
    stock = {"installed": installed_model(local, "stock.valuation.layer")}
    if stock["installed"]:
        svl = local["stock.valuation.layer"].with_company(company)
        # SVL create_date and GL accounting date are different clocks. Report this
        # as a current diagnostic; never label it a historical GL reconciliation.
        stock["current_valuation_totals_not_historical"] = svl.read_group(company_domain,
            ["product_id", "quantity:sum", "value:sum"], ["product_id"], lazy=False)
        automated = company_domain + [("product_id.categ_id.property_valuation", "=", "real_time"),
                                      ("value", "!=", 0), ("account_move_id", "=", False)]
        stock["automated_nonzero_layers_without_direct_account_move_review_count"] = svl.search_count(automated)
        stock["interpretation"] = "Review candidates only: related correction layers and historical valuation-policy changes require inspection."
        stock["review_sample"] = records(svl, automated,
            ["product_id", "stock_move_id", "account_move_id", "stock_valuation_layer_id", "value", "quantity", "create_date"], sample_limit)
    categories = []
    if installed_model(local, "product.category"):
        cat_model = local["product.category"].with_company(company)
        candidates = cat_model.search([])
        property_names = ("property_valuation", "property_cost_method", "property_stock_valuation_account_id",
                          "property_stock_account_input_categ_id", "property_stock_account_output_categ_id",
                          "property_account_income_categ_id", "property_account_expense_categ_id")
        for category in candidates:
            row = {"id": category.id, "name": category.name}
            for name in property_names:
                if name in category._fields:
                    value = category[name]
                    row[name] = value.id if category._fields[name].type == "many2one" else value
            categories.append(row)
    product_diagnostics = {}
    if installed_model(local, "product.product"):
        products = local["product.product"].with_company(company)
        product_domain = [("company_id", "in", [False, company.id]), ("type", "=", "product")]
        zero_domain = product_domain + [("standard_price", "=", 0)]
        product_diagnostics = {
            "stockable_product_count": products.search_count(product_domain),
            "zero_current_cost_review_count": products.search_count(zero_domain),
            "interpretation": "Current zero cost is not proof of zero historical valuation; inspect original SVLs and approved policy.",
            "zero_cost_sample": records(products, zero_domain, ["default_code", "categ_id", "active", "standard_price"], sample_limit),
        }
    return {
        "company_id": company.id, "company_name": company.name,
        "currency": company.currency_id.name, "currency_rounding": company.currency_id.rounding,
        "anglo_saxon_accounting": company.anglo_saxon_accounting if "anglo_saxon_accounting" in company._fields else None,
        "fiscal_year": fy, "accounts": accounts,
        "duplicate_account_codes": duplicate_account_codes(accounts),
        "posted_trial_balance_as_of": closing,
        "trial_balance_check": balance_summary(closing, company.currency_id.rounding),
        "fiscal_ytd_pnl_account_balances": pnl,
        "fiscal_ytd_revenue_without_product": revenue_no_product,
        "draft_journal_item_count_as_of": aml.search_count(company_domain + [("parent_state", "=", "draft"), ("date", "<=", report_date)]),
        "first_posted_accounting_date": aml.search(posted, order="date,id", limit=1).date or None,
        "categories_resolved_for_company": categories, "products": product_diagnostics, "stock": stock,
        "opening_balances_customer_approved": "NOT_VERIFIED",
        "stock_to_gl_historical_reconciliation": "NOT_RUN",
    }


def collect(env, report_date, sample_limit=50):
    if not isinstance(report_date, dt.date):
        raise ValueError("report_date must be a date")
    if not 1 <= sample_limit <= 1000:
        raise ValueError("sample_limit must be between 1 and 1000")
    # No sudo: preserve the shell user's actual authorized company scope.
    companies = env.companies
    modules = records(env["ir.module.module"], [("state", "=", "installed")],
                      ["name", "latest_version", "state"])
    installed_names = {item["name"] for item in modules}
    model_fields = {}
    tokens = ("requisition", "maintenance", "repair", "quality", "labour", "labor", "capex", "financial")
    for name in sorted(env.registry.models):
        if any(token in name for token in tokens):
            model = env[name]
            model_fields[name] = {
                fname: {"type": field.type, "relation": getattr(field, "comodel_name", None),
                    "selection": field.selection if isinstance(getattr(field, "selection", None), (list, tuple)) else None}
                for fname, field in model._fields.items()
                if any(token in fname for token in ("account", "journal", "move", "valuation", "company", "capex", "opex", "maintenance_for", "workcenter", "equipment", "repair", "labour", "labor"))
            }
    result = {
        "schema_version": 1, "status": "PREFLIGHT_ONLY_NOT_PRODUCTION_CERTIFIED",
        "report_date": report_date, "scope": "authorized companies only",
        "installed_modules": modules,
        "module_availability": {name: name in installed_names for name in CORE_MODULES},
        "custom_integration_model_fields": model_fields,
        "posting_override_chains": {
            "stock.move": method_origins(env, "stock.move", ["_action_done", "_get_accounting_data_for_valuation", "_account_entry_move"]),
            "mrp.production": method_origins(env, "mrp.production", ["_cal_price", "button_mark_done", "_get_moves_finished_values"]),
            "repair.order": method_origins(env, "repair.order", ["action_repair_end"]),
        },
        "companies": [company_snapshot(env, company, report_date, sample_limit) for company in companies],
        "workflow_tests": {key: {"state": "NOT_RUN", "acceptance": value} for key, value in WORKFLOWS.items()},
        "live_report_reconciliation": "NOT_RUN",
        "source_data_complete": "NOT_VERIFIED",
    }
    if installed_model(env, "account.report"):
        result["native_reports"] = records(env["account.report"], [],
            ["name", "active", "root_report_id", "filter_hierarchy", "column_ids", "line_ids", "custom_handler_model_id"])
        result["native_report_method_signatures"] = method_origins(env, "account.report", ["get_options", "_get_lines", "get_pdf", "get_xlsx", "_get_report_query"])
        result["native_expression_schema"] = {name: field.type for name, field in env["account.report.expression"]._fields.items()}
        result["native_expressions"] = records(env["account.report.expression"], [],
            ["report_line_id", "label", "engine", "formula", "subformula", "date_scope"], 10000)
        result["native_expressions_truncated"] = env["account.report.expression"].search_count([]) > 10000
    else:
        result["native_reports"] = None
    return result


def run_read_only(shell_env, date, expected_database=EXPECTED_DATABASE, sample_limit=50):
    """A separate read-only PostgreSQL transaction protects business data."""
    if shell_env is None:
        raise RuntimeError("Run this script from Odoo shell, where env is available.")
    if shell_env.cr.dbname != expected_database:
        raise RuntimeError("Database mismatch; no audit was run.")
    from odoo import api, release
    if str(release.version_info[0]) != "17":
        raise RuntimeError("This audit targets Odoo 17 only.")
    with shell_env.registry.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        try:
            local_env = api.Environment(cursor, shell_env.uid, dict(shell_env.context, active_test=False))
            result = collect(local_env, date, sample_limit)
            result["database"] = expected_database
            result["odoo_version"] = release.version
            result["read_only_transaction"] = True
            return result
        finally:
            cursor.rollback()


def save_private_json(result, path):
    """Never overwrite an existing audit or publish it into the source repository."""
    target = Path(path).expanduser().resolve()
    for directory in [target.parent, *target.parent.parents]:
        if (directory / ".git").exists():
            raise RuntimeError("Choose an audit output outside a Git working tree.")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, indent=2, default=str, ensure_ascii=False, allow_nan=False)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(target), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.write("\n")
    return target


def main(shell_env=None):
    date = dt.date.fromisoformat(os.environ.get("LEGACY_AUDIT_DATE", "2025-12-31"))
    result = run_read_only(shell_env, date)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = os.environ.get("LEGACY_AUDIT_OUTPUT", str(Path.home() / "LegacyLocalAudit" / f"finance-preflight-{stamp}.json"))
    target = save_private_json(result, output)
    print(f"Read-only preflight written to {target}. Financial workflow tests and report reconciliation have NOT run.")


if __name__ == "__main__":
    main(globals().get("env"))
