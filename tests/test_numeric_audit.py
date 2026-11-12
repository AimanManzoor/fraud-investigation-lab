import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from src.audit_numeric import FIELDS, audit_numeric


class NumericAuditTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / "test.db"
        with closing(sqlite3.connect(self.db)) as connection, connection:
            definition = ",".join(f'"{name}" TEXT' for name in FIELDS)
            connection.execute(
                f"CREATE TABLE raw_transactions ({definition})"
            )

    def load(self, rows):
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.executemany(
                "INSERT INTO raw_transactions VALUES (?,?,?,?,?,?)", rows
            )

    def audit(self):
        with redirect_stdout(io.StringIO()):
            return audit_numeric(self.db)

    def test_valid_values_and_unchanged_database(self):
        self.load([("1", "9839.64", "0", "100.00", "0", "1e3")])
        before = self.db.read_bytes()
        report = self.audit()

        self.assertEqual(report["rows_checked"], 1)
        self.assertEqual(report["numeric_status"], "passed")
        self.assertEqual(report["invalid_cells"], 0)
        self.assertTrue(all(
            result["valid"] == 1
            for result in report["columns"].values()
        ))
        self.assertEqual(self.db.read_bytes(), before)

    def test_invalid_cells_are_classified_without_dropping_records(self):
        self.load([
            ("1", "10", "0", "0", "0", "0"),
            ("1.5", "-5", "bad", "NaN", None, "1e999"),
        ])
        report = self.audit()

        self.assertEqual(report["rows_checked"], 2)
        self.assertEqual(report["numeric_status"], "issues_found")
        self.assertEqual(report["invalid_cells"], 6)

        expected = [
            "not_integer_literal", "negative", "not_numeric",
            "non_finite", "missing", "out_of_range",
        ]
        for name, issue in zip(FIELDS, expected):
            result = report["columns"][name]
            self.assertEqual(result["valid"], 1)
            self.assertEqual(result["invalid"], 1)
            self.assertEqual(result["issue_counts"][issue], 1)

    def test_empty_table_is_not_reported_as_passed(self):
        report = self.audit()
        self.assertEqual(report["numeric_status"], "empty")
        self.assertEqual(report["rows_checked"], 0)

    def test_missing_database_is_not_created(self):
        path = self.db.with_name("missing.db")
        with self.assertRaises(FileNotFoundError):
            audit_numeric(path)
        self.assertFalse(path.exists())

    def test_missing_schema_is_rejected(self):
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("DROP TABLE raw_transactions")
        with self.assertRaises(ValueError):
            self.audit()


if __name__ == "__main__":
    unittest.main()
