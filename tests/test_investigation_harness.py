import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.explorer import explore
from src.investigation_harness import main, run_plan
from tests import test_demo, test_explorer


class HarnessTests(unittest.TestCase):
    def setUp(self):
        fixture = test_explorer.ExplorerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.database = fixture.database
        self.plan = {
            "tool": "search_account", "account_id": "A", "limit": 20
        }

    def run_full(self, plan=None):
        return run_plan(
            "A", self.plan if plan is None else plan,
            self.database, source_kind="full"
        )

    def test_completed_run_preserves_data_and_hides_labels(self):
        before = self.database.read_bytes()
        receipt = self.run_full()
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["matching_transactions"], 2)
        self.assertEqual(receipt["tool_calls"], 1)
        self.assertTrue(receipt["human_review_required"])
        self.assertEqual(
            receipt["evidence"][0]["source_ref"], "full:transactions:1"
        )
        self.assertNotIn("is_fraud", receipt["evidence"][0])
        self.assertNotIn("legacy_flag", receipt["evidence"][0])
        self.assertEqual(before, self.database.read_bytes())

    def test_rejects_scope_tool_budget_and_extra_arguments_before_query(self):
        proposals = [
            dict(self.plan, account_id="B"),
            dict(self.plan, tool="execute_sql"),
            dict(self.plan, limit=51),
            dict(self.plan, limit=True),
            dict(self.plan, sql="DELETE FROM transactions"),
            [],
        ]
        with patch("src.investigation_harness.explore") as tool:
            for proposal in proposals:
                with self.subTest(proposal=proposal):
                    receipt = self.run_full(proposal)
                    self.assertEqual(receipt["status"], "rejected")
                    self.assertEqual(receipt["tool_calls"], 0)
            tool.assert_not_called()

    def test_missing_database_is_not_a_completed_investigation(self):
        receipt = run_plan(
            "A", self.plan, self.database.with_name("missing.db"),
            source_kind="full",
        )
        self.assertEqual(receipt["status"], "tool_error")
        self.assertEqual(
            receipt["steps"][-1]["error_type"], "FileNotFoundError"
        )

    def test_no_matches_is_not_a_fraud_verdict(self):
        plan = dict(self.plan, account_id="missing")
        receipt = run_plan(
            "missing", plan, self.database, source_kind="full"
        )
        self.assertEqual(receipt["status"], "no_matches")
        self.assertEqual(receipt["evidence"], [])
        self.assertTrue(receipt["human_review_required"])

    def test_out_of_scope_evidence_is_rejected(self):
        result = explore(self.database, account_id="A")
        result["rows"][0].update(origin_id="X", destination_id="Y")
        with patch(
            "src.investigation_harness.explore", return_value=result
        ):
            receipt = self.run_full()
        self.assertEqual(receipt["status"], "verification_failed")
        self.assertNotIn("evidence", receipt)

    def test_inconsistent_totals_and_duplicate_references_are_rejected(self):
        for mutation in ("total", "duplicate"):
            result = explore(self.database, account_id="A")
            if mutation == "total":
                result["total"] = 100
            else:
                result["rows"][1]["record_id"] = result["rows"][0]["record_id"]
            with self.subTest(mutation=mutation):
                with patch(
                    "src.investigation_harness.explore",
                    return_value=result,
                ):
                    self.assertEqual(
                        self.run_full()["status"], "verification_failed"
                    )

    def test_tool_failure_does_not_retry(self):
        with patch(
            "src.investigation_harness.explore",
            side_effect=sqlite3.OperationalError("private detail"),
        ) as tool:
            receipt = self.run_full()
        self.assertEqual(receipt["status"], "tool_error")
        tool.assert_called_once()
        self.assertNotIn("private detail", str(receipt))

    def test_demo_has_explicit_partial_history(self):
        fixture = test_demo.DemoTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        from src.demo import export_demo
        export_demo(fixture.database, fixture.sample)
        fixture.database.unlink()
        receipt = run_plan("A", self.plan, fixture.sample)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["partial_history"])
        self.assertEqual(receipt["matching_transactions"], 2)

    def test_cli_saves_a_receipt(self):
        fixture = test_demo.DemoTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        from src.demo import export_demo
        root = fixture.database.parent
        export_demo(fixture.database, root / "demo/transactions.json")
        with patch(
            "src.investigation_harness.__file__",
            str(root / "src/investigation_harness.py"),
        ), patch(
            "sys.argv", ["harness", "--account-id", "A"]
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 0)

        paths = list(
            (root / "reports/generated/harness_runs").glob("*.json")
        )
        self.assertEqual(len(paths), 1)
        saved = json.loads(paths[0].read_text())
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["planning_mode"], "deterministic_default")
        self.assertEqual(saved["tool_calls"], 1)
