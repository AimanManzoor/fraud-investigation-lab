import sqlite3
import unittest

from streamlit.testing.v1 import AppTest

from src.demo import export_demo, explore_demo
from src.explorer import explore
from tests import test_explorer


class AccountSearchTests(unittest.TestCase):
    def setUp(self):
        fixture = test_explorer.ExplorerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.database = fixture.database

    def test_sender_recipient_and_other_filters(self):
        self.assertEqual(explore(self.database, account_id="A")["total"], 2)
        self.assertEqual(explore(self.database, account_id="B")["total"], 1)
        self.assertEqual(
            explore(self.database, account_id="A", fraud=1)["total"], 1
        )
        self.assertEqual(
            explore(self.database, account_id="A", kind="PAYMENT")["total"], 0
        )

    def test_account_text_is_a_literal_parameter(self):
        account = "x' OR 1=1 --"
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                (5, 1, "TRANSFER", 100, account, "Z", 0, 0),
            )
        result = explore(self.database, account_id=account)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["record_id"], 5)
        self.assertEqual(explore(self.database, account_id="a")["total"], 0)

    def test_same_account_on_both_sides_is_counted_once(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                (5, 1, "TRANSFER", 100, "A", "A", 0, 0),
            )
        result = explore(self.database, account_id="A", limit=1)
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["rows"]), 1)

    def test_invalid_account_filters(self):
        for account in ("", " ", 12, True, "A" * 129):
            with self.subTest(account=account):
                with self.assertRaises(ValueError):
                    explore(self.database, account_id=account)

    def test_demo_account_search_without_full_database(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE build_metadata(report_json TEXT)")
            connection.execute(
                "INSERT INTO build_metadata VALUES (?)",
                ('{"source_csv_sha256":"fixture"}',),
            )
        sample = self.database.with_suffix(".json")
        export_demo(self.database, sample)
        self.database.unlink()
        self.assertEqual(explore_demo(sample, account_id="A")["total"], 2)
        self.assertEqual(explore_demo(sample, account_id="B")["total"], 1)

    def test_ui_search_and_clear(self):
        app = AppTest.from_string(
            "from app import main\nmain(" + repr(str(self.database)) + ")"
        ).run()
        field = next(
            item for item in app.text_input
            if item.label == "Account ID (optional)"
        )
        field.set_value("A")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "2")

        field = next(
            item for item in app.text_input
            if item.label == "Account ID (optional)"
        )
        field.set_value("B")
        app.button[0].click().run()
        self.assertEqual(app.metric[0].value, "1")

        field = next(
            item for item in app.text_input
            if item.label == "Account ID (optional)"
        )
        field.set_value("")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "4")
