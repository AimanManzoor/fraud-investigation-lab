import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from src.ingest import FIELDS, ingest


class IngestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.csv = self.root / "sample.csv"
        self.db = self.root / "data/fraud.db"
        self.report = self.root / "reports/quality.json"
        self.row = [
            "1", "TRANSFER", "100.00", "C1", "100", "0",
            "C2", "0", "100", "1", "0"
        ]

    def write_csv(self, rows, header=FIELDS):
        with self.csv.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def load(self):
        with redirect_stdout(io.StringIO()):
            return ingest(self.csv, self.db, self.report)

    def test_batches_preserve_records_values_and_source(self):
        self.write_csv([self.row] * 5001)
        original = self.csv.read_bytes()
        report = self.load()

        self.assertEqual(report["csv_records"], 5001)
        self.assertEqual(report["sqlite_records"], 5001)
        self.assertEqual(self.csv.read_bytes(), original)
        self.assertEqual(
            report["source_sha256"],
            hashlib.sha256(original).hexdigest()
        )
        with sqlite3.connect(self.db) as connection:
            value = connection.execute(
                "SELECT amount, typeof(amount) "
                "FROM raw_transactions LIMIT 1"
            ).fetchone()
        self.assertEqual(value, ("100.00", "text"))
        self.assertEqual(json.loads(self.report.read_text()), report)

    def test_invalid_values_are_reported_without_removing_rows(self):
        bad = self.row.copy()
        bad[0], bad[2], bad[9] = " ", "not-a-number", "bad"
        self.write_csv([self.row, bad])
        report = self.load()

        self.assertEqual(report["sqlite_records"], 2)
        self.assertEqual(report["blank_or_space_counts"]["step"], 1)
        self.assertEqual(report["invalid_label_counts"]["isFraud"], 1)
        self.assertIn("numeric types and ranges", report["pending_checks"])

    def test_bad_header_does_not_publish_database(self):
        self.write_csv([self.row], header=["wrong"])
        with self.assertRaises(ValueError):
            self.load()
        self.assertFalse(self.db.exists())
        self.assertFalse(
            self.db.with_name(self.db.name + ".building").exists()
        )

    def test_malformed_record_after_batch_does_not_publish_database(self):
        self.write_csv([self.row] * 5000 + [["too", "short"]])
        with self.assertRaises(ValueError):
            self.load()
        self.assertFalse(self.db.exists())
        self.assertFalse(self.report.exists())

    def test_existing_database_is_preserved(self):
        self.write_csv([self.row])
        self.load()
        original = self.db.read_bytes()

        with self.assertRaises(FileExistsError):
            self.load()
        self.assertEqual(self.db.read_bytes(), original)

    def test_empty_csv_and_conflicting_output_paths_are_rejected(self):
        self.write_csv([])
        with self.assertRaises(ValueError):
            self.load()
        self.assertFalse(self.db.exists())

        with self.assertRaises(ValueError):
            ingest(self.csv, self.db, self.db)


if __name__ == "__main__":
    unittest.main()
