import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.explorer import explore, format_amount


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "typed.db"

        with sqlite3.connect(self.database) as connection:
            connection.execute("""CREATE TABLE transactions (
                record_id INTEGER PRIMARY KEY,
                step INTEGER,
                transaction_type TEXT,
                amount_minor INTEGER,
                origin_id TEXT,
                destination_id TEXT,
                is_fraud INTEGER,
                legacy_flag INTEGER
            )""")
            connection.executemany(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                [
                    (1, 1, "TRANSFER", 101, "A", "B", 1, 0),
                    (2, 2, "TRANSFER", 200, "A", "C", 0, 1),
                    (3, 3, "PAYMENT", 300, "D", "E", 0, 0),
                    (4, 2, "TRANSFER", 201, "F", "G", 1, 0),
                ],
            )

    def test_full_totals_independent_of_display_limit(self):
        result = explore(self.database, limit=1)
        self.assertEqual((result["total"], len(result["rows"])), (4, 1))
        self.assertEqual(
            (result["fraud_labels"], result["legacy_flags"]), (2, 1)
        )
        self.assertEqual(
            sum(group["records"] for group in result["groups"]), 4
        )

    def test_combined_filters_and_inclusive_boundaries(self):
        result = explore(
            self.database,
            kind="TRANSFER",
            step_min=2,
            step_max=2,
            amount_min="2.00",
            amount_max="2.01",
            fraud=1,
            legacy=0,
        )
        self.assertEqual(
            [row["record_id"] for row in result["rows"]], [4]
        )
        self.assertEqual(result["rows"][0]["amount"], "2.01")

    def test_labels_are_independent(self):
        self.assertEqual(explore(self.database, fraud=1)["total"], 2)
        self.assertEqual(explore(self.database, legacy=1)["total"], 1)
        self.assertEqual(
            explore(self.database, fraud=1, legacy=1)["total"], 0
        )

    def test_no_matches(self):
        result = explore(self.database, amount_min="10")
        self.assertEqual(
            (result["total"], result["rows"], result["groups"]),
            (0, [], []),
        )

    def test_invalid_filters_rejected(self):
        cases = (
            {"kind": "TRANSFER' OR 1=1 --"},
            {"fraud": 2},
            {"legacy": True},
            {"step_min": 0},
            {"step_min": 1.5},
            {"step_max": 2**63},
            {"step_min": 3, "step_max": 2},
            {"amount_min": "0.001"},
            {"amount_min": "NaN"},
            {"amount_min": "3", "amount_max": "2"},
            {"limit": 501},
        )
        for filters in cases:
            with self.subTest(filters=filters):
                with self.assertRaises(ValueError):
                    explore(self.database, **filters)

    def test_missing_database_is_not_created(self):
        missing = self.database.with_name("missing.db")
        with self.assertRaises(FileNotFoundError):
            explore(missing)
        self.assertFalse(missing.exists())

    def test_database_is_unchanged(self):
        before = self.database.read_bytes()
        explore(self.database, kind="TRANSFER")
        self.assertEqual(before, self.database.read_bytes())

    def test_large_amount_display_stays_exact(self):
        self.assertEqual(
            format_amount(9007199254740993),
            "90,071,992,547,409.93",
        )


if __name__ == "__main__":
    unittest.main()
