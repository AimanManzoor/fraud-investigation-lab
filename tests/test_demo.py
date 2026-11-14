import json
import sqlite3
import unittest

from streamlit.testing.v1 import AppTest

from src.demo import export_demo, explore_demo
from tests import test_explorer


class DemoTests(unittest.TestCase):
    def setUp(self):
        fixture = test_explorer.ExplorerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.database = fixture.database
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE build_metadata(report_json TEXT)")
            connection.execute(
                "INSERT INTO build_metadata VALUES (?)",
                (json.dumps({"source_csv_sha256": "fixture-hash"}),),
            )
        self.sample = self.database.with_suffix(".json")

    def test_export_is_reproducible_and_source_unchanged(self):
        before = self.database.read_bytes()
        report = export_demo(self.database, self.sample)
        other = self.sample.with_name("other.json")
        export_demo(self.database, other)
        self.assertEqual(report["sample_records"], 4)
        self.assertEqual(self.sample.read_bytes(), other.read_bytes())
        self.assertEqual(before, self.database.read_bytes())
        self.assertEqual(
            json.loads(self.sample.read_text())["source_csv_sha256"],
            "fixture-hash",
        )

    def test_demo_queries_without_full_database(self):
        export_demo(self.database, self.sample)
        self.database.unlink()
        result = explore_demo(self.sample, fraud=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["rows"][0]["amount"], "1.01")

    def test_existing_sample_is_preserved(self):
        self.sample.write_text("keep")
        with self.assertRaises(FileExistsError):
            export_demo(self.database, self.sample)
        self.assertEqual(self.sample.read_text(), "keep")

    def test_missing_sample_and_database_do_not_get_created(self):
        with self.assertRaises(FileNotFoundError):
            explore_demo(self.sample)
        missing = self.database.with_name("missing.db")
        with self.assertRaises(FileNotFoundError):
            export_demo(missing, self.sample)
        self.assertFalse(missing.exists())
        self.assertFalse(self.sample.exists())

    def test_invalid_sample_rejected(self):
        export_demo(self.database, self.sample)
        original = json.loads(self.sample.read_text())
        for mutate in (
            lambda p: p.update(format_version=2),
            lambda p: p["rows"][0].__setitem__(3, 1.5),
            lambda p: p["rows"].append(p["rows"][0]),
        ):
            payload = json.loads(json.dumps(original))
            mutate(payload)
            self.sample.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                explore_demo(self.sample)

    def test_hosted_ui_without_full_database_and_source_switch(self):
        root = self.database.parent
        sample = root / "demo/transactions.json"
        export_demo(self.database, sample)
        missing = root / "data/fraud_typed.db"
        script = (
            "from pathlib import Path\nfrom unittest.mock import patch\n"
            "from app import main\nwith patch('app.DEFAULT_DATABASE', Path("
            + repr(str(missing)) + ")):\n    main()\n"
        )
        app = AppTest.from_string(script).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.radio[0].value, "Demo sample")
        self.assertIn("not representative", app.warning[0].value)

        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "4")

        app.radio[0].set_value("Full local database").run()
        self.assertEqual(len(app.metric), 0)
        app.button[0].click().run()
        self.assertIn("Typed database missing", app.error[0].value)

        app.radio[0].set_value("Demo sample").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "4")
