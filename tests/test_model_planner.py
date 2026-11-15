import io
import json
import shutil
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from src.model_planner import API_URL, NoRedirect, investigate, main
from tests import test_explorer


class ModelPlannerTests(unittest.TestCase):
    def setUp(self):
        fixture = test_explorer.ExplorerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.database = fixture.database
        self.plan = {"tool": "search_account", "account_id": "A", "limit": 20}

    def response(self, plan=None, **extra):
        message = {"model": "test-model-snapshot", "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(
            self.plan if plan is None else plan)}], "usage": {"input_tokens": 20, "output_tokens": 10}}
        message.update(extra)
        return io.BytesIO(json.dumps(message).encode())

    def run_case(self, transport, **overrides):
        kwargs = dict(model="test-model", api_key="unit-test-secret", source_kind="full", transport=transport)
        kwargs.update(overrides)
        return investigate("A", "Show ten transactions for this account", self.database, **kwargs)

    def test_valid_plan_uses_harness_without_sending_database_rows(self):
        transport = Mock(return_value=self.response())
        before = self.database.read_bytes()
        result = self.run_case(transport)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["planner"]["request_attempts"], 1)
        self.assertEqual(result["planner"]["model_returned"], "test-model-snapshot")
        request = transport.call_args.args[0]
        self.assertEqual(request.full_url, API_URL)
        payload = json.loads(request.data)
        self.assertEqual(payload["max_tokens"], 256)
        sent = json.loads(payload["messages"][0]["content"])
        self.assertEqual(set(sent), {"question", "account_id", "source_kind"})
        self.assertNotIn("unit-test-secret", json.dumps(result))
        self.assertEqual(before, self.database.read_bytes())

    def test_bad_model_proposals_never_call_evidence_tool(self):
        for plan in (dict(self.plan, account_id="B"), dict(self.plan, tool="execute_sql"),
                     dict(self.plan, limit=500), dict(self.plan, source="private.db")):
            with self.subTest(plan=plan), patch("src.investigation_harness.explore") as tool:
                result = self.run_case(Mock(return_value=self.response(plan)))
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["tool_calls"], 0)
                tool.assert_not_called()

    def test_malformed_duplicate_or_truncated_outputs_do_not_query(self):
        for text, stop in (("not JSON", "end_turn"),
                           ('{"tool":"search_account","tool":"execute_sql"}', "end_turn"),
                           (json.dumps(self.plan), "max_tokens")):
            response = self.response(content=[{"type": "text", "text": text}], stop_reason=stop)
            with self.subTest(text=text), patch("src.investigation_harness.explore") as tool:
                result = self.run_case(Mock(return_value=response))
                self.assertEqual(result["status"], "planner_error")
                tool.assert_not_called()

    def test_rate_limit_does_not_retry_or_expose_provider_body(self):
        transport = Mock(side_effect=HTTPError(API_URL, 429, "private provider detail", {}, None))
        result = self.run_case(transport)
        self.assertEqual(result["status"], "planner_error")
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(result["planner"]["http_status"], 429)
        transport.assert_called_once()
        self.assertNotIn("private provider detail", json.dumps(result))

    def test_missing_key_or_source_stops_before_request(self):
        transport = Mock()
        self.assertEqual(self.run_case(transport, api_key="")["planner"]["request_attempts"], 0)
        self.database.unlink()
        self.assertEqual(self.run_case(transport)["planner"]["request_attempts"], 0)
        transport.assert_not_called()

    def test_oversized_response_is_rejected(self):
        result = self.run_case(Mock(return_value=io.BytesIO(b"x" * 65537)))
        self.assertEqual(result["status"], "planner_error")
        self.assertEqual(result["tool_calls"], 0)

    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.org"))

    def test_cli_saves_receipt_without_exposing_key(self):
        root = self.database.parent
        target = root / "data/fraud_typed.db"
        target.parent.mkdir()
        shutil.copyfile(self.database, target)
        transport = Mock(return_value=self.response())
        output = io.StringIO()
        with patch("src.model_planner.__file__", str(root / "src/model_planner.py")), \
             patch("sys.argv", ["planner", "--live", "--account-id", "A", "--source", "full",
                                 "--model", "test-model", "--question", "Show transactions"]), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "unit-test-secret"}), \
             patch("src.model_planner.build_opener", return_value=Mock(open=transport)), \
             redirect_stdout(output):
            self.assertEqual(main(), 0)
        paths = list((root / "reports/generated/harness_runs").glob("*.json"))
        self.assertEqual(len(paths), 1)
        saved = json.loads(paths[0].read_text())
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["planner"]["request_attempts"], 1)
        self.assertNotIn("unit-test-secret", output.getvalue())
