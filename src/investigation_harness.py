"""Bounded execution of proposed plans; optional model adapter: src/model_planner.py."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.demo import explore_demo
from src.explorer import TYPES, explore, format_amount
from src.money import MAX_INTEGER, to_minor_units


def verify_evidence(result, account_id, limit):
    total, rows, groups = result["total"], result["rows"], result["groups"]
    if type(total) is not int or total < 0:
        raise ValueError("Invalid total.")
    if not isinstance(rows, list) or len(rows) != min(total, limit):
        raise ValueError("Displayed row count is inconsistent.")
    if any(group["transaction_type"] not in TYPES or
           type(group["records"]) is not int or group["records"] < 0 for group in groups):
        raise ValueError("Invalid transaction counts.")
    if sum(group["records"] for group in groups) != total:
        raise ValueError("Group counts disagree with total.")

    seen = set()
    for row in rows:
        rid = row["record_id"]
        if type(rid) is not int or rid <= 0 or rid in seen:
            raise ValueError("Invalid or repeated evidence reference.")
        if account_id not in (row["origin_id"], row["destination_id"]):
            raise ValueError("Evidence falls outside the requested account.")
        if (type(row["step"]) is not int or not 1 <= row["step"] <= MAX_INTEGER
                or row["transaction_type"] not in TYPES or not isinstance(row["amount"], str)):
            raise ValueError("Invalid evidence fields.")
        if format_amount(to_minor_units(row["amount"].replace(",", ""))) != row["amount"]:
            raise ValueError("Invalid amount format.")
        seen.add(rid)


def run_plan(account_id, plan, source, *, source_kind="demo"):
    receipt = {
        "run_id": str(uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_kind": source_kind,
        "status": "rejected",
        "tool_calls": 0,
        "tool_budget": 1,
        "human_review_required": True,
        "steps": [],
    }
    valid = (
        isinstance(account_id, str) and bool(account_id.strip()) and len(account_id) <= 128
        and source_kind in ("demo", "full") and isinstance(plan, dict)
        and set(plan) == {"tool", "account_id", "limit"}
        and plan["tool"] == "search_account" and plan["account_id"] == account_id
        and type(plan["limit"]) is int and 1 <= plan["limit"] <= 50
    )
    if not valid:
        receipt["steps"].append({"stage": "validate_plan", "status": "rejected"})
        receipt["message"] = "Plan must use search_account for the requested account with limit 1-50."
        return receipt

    receipt["account_id"] = account_id
    receipt["steps"].append({"stage": "validate_plan", "status": "passed"})
    tool = explore_demo if source_kind == "demo" else explore
    receipt["tool_calls"] = 1

    try:
        result = tool(source, account_id=account_id, limit=plan["limit"])
    except (FileNotFoundError, sqlite3.Error, ValueError) as error:
        receipt["status"] = "tool_error"
        receipt["steps"].append({
            "stage": "search_account",
            "status": "failed",
            "error_type": type(error).__name__,
        })
        return receipt

    receipt["steps"].append({"stage": "search_account", "status": "completed"})

    try:
        verify_evidence(result, account_id, plan["limit"])
    except (KeyError, TypeError, ValueError) as error:
        receipt["status"] = "verification_failed"
        receipt["steps"].append({
            "stage": "verify_evidence",
            "status": "failed",
            "error_type": type(error).__name__,
        })
        return receipt

    receipt["steps"].append({"stage": "verify_evidence", "status": "passed"})
    receipt["status"] = "completed" if result["total"] else "no_matches"
    receipt["matching_transactions"] = result["total"]

    fields = (
        "record_id", "step", "transaction_type",
        "amount", "origin_id", "destination_id",
    )
    receipt["evidence"] = [
        dict(
            {key: row[key] for key in fields},
            source_ref=f"{source_kind}:transactions:{row['record_id']}",
        )
        for row in result["rows"]
    ]
    receipt["partial_history"] = source_kind == "demo"
    receipt["message"] = (
        "Account scope and count consistency checked. "
        "Fraud risk has not been assessed."
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--source", choices=("demo", "full"), default="demo")
    parser.add_argument(
        "--plan-json",
        help="Optional proposed plan to validate; no model is called.",
    )
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan_json) if args.plan_json is not None else {
            "tool": "search_account",
            "account_id": args.account_id,
            "limit": 20,
        }
    except json.JSONDecodeError:
        parser.error("The proposed plan is not valid JSON.")

    root = Path(__file__).resolve().parents[1]
    source = root / (
        "demo/transactions.json"
        if args.source == "demo" else "data/fraud_typed.db"
    )
    receipt = run_plan(
        args.account_id, plan, source, source_kind=args.source
    )
    receipt["planning_mode"] = (
        "provided_plan" if args.plan_json is not None
        else "deterministic_default"
    )

    output = (
        root / "reports/generated/harness_runs"
        / (receipt["run_id"] + ".json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)

    print(json.dumps(receipt, indent=2))
    print("Receipt saved:", output)
    return 0 if receipt["status"] in ("completed", "no_matches") else 1


if __name__ == "__main__":
    raise SystemExit(main())
