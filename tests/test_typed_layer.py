import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from src.build_typed import build_typed, convert_record


class TypedLayerTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.raw = Path(folder.name) / "raw.db"
        self.output = Path(folder.name) / "typed.db"
        self.row = (
            1, "1", "TRANSFER", "9839.64", "C1", "C2", "1", "0"
        )

        with closing(sqlite3.connect(self.raw)) as connection, connection:
            connection.execute(
                "CREATE TABLE raw_transactions ("
                "record_id INTEGER PRIMARY KEY, step TEXT, "
                '"type" TEXT, amount TEXT, nameOrig TEXT, '
                "nameDest TEXT, isFraud TEXT, isFlaggedFraud TEXT)"
            )
            connection.execute(
                "CREATE TABLE ingestion_metadata (report_json TEXT)"
            )
            connection.execute(
                "INSERT INTO ingestion_metadata VALUES (?)",
                (json.dumps({"source_sha256": "fixture-hash"}),),
            )

    def load(self, rows):
        with closing(sqlite3.connect(self.raw)) as connection, connection:
            connection.executemany(
                "INSERT INTO raw_transactions VALUES (?,?,?,?,?,?,?,?)",
                rows,
            )

    def build(self):
        with redirect_stdout(io.StringIO()):
            return build_typed(self.raw, self.output)

    def test_exact_conversion_counts_and_source_preservation(self):
        self.load([self.row, (2, *self.row[1:])])
        before = self.raw.read_bytes()
        report = self.build()

        self.assertEqual(report["source_records"], 2)
        self.assertEqual(report["typed_records"], 2)
        self.assertEqual(report["source_csv_sha256"], "fixture-hash")

        with closing(sqlite3.connect(self.output)) as connection:
            row = connection.execute(
                "SELECT amount_minor, typeof(amount_minor), "
                "step, typeof(step), is_fraud, legacy_flag "
                "FROM transactions WHERE record_id=1"
            ).fetchone()
            saved = json.loads(connection.execute(
                "SELECT report_json FROM build_metadata"
            ).fetchone()[0])

        self.assertEqual(row, (983964, "integer", 1, "integer", 1, 0))
        self.assertEqual(saved, report)
        self.assertEqual(self.raw.read_bytes(), before)

    def test_invalid_fields_are_rejected(self):
        cases = [
            (1, "0"), (2, "UNKNOWN"), (3, "0.001"),
            (4, ""), (5, None), (6, "bad"), (7, "2"),
        ]
        for index, invalid in cases:
            with self.subTest(index=index):
                row = list(self.row)
                row[index] = invalid
                with self.assertRaises(ValueError):
                    convert_record(row)

    def test_precision_error_never_publishes_partial_database(self):
        rows = [
            (number, *self.row[1:]) for number in range(1, 5001)
        ]
        rows.append(
            (5001, "1", "TRANSFER", "0.001", "C1", "C2", "1", "0")
        )
        self.load(rows)
        before = self.raw.read_bytes()

        with self.assertRaises(ValueError):
            self.build()

        self.assertFalse(self.output.exists())
        self.assertFalse(
            self.output.with_name(self.output.name + ".building").exists()
        )
        self.assertEqual(self.raw.read_bytes(), before)

    def test_existing_destination_is_preserved(self):
        self.load([self.row])
        self.build()
        before = self.output.read_bytes()

        with self.assertRaises(FileExistsError):
            self.build()

        self.assertEqual(self.output.read_bytes(), before)

    def test_missing_source_is_not_created(self):
        missing = self.raw.with_name("missing.db")
        with self.assertRaises(FileNotFoundError):
            build_typed(missing, self.output)
        self.assertFalse(missing.exists())
        self.assertFalse(self.output.exists())

    def test_same_path_and_empty_source_are_rejected(self):
        with self.assertRaises(ValueError):
            build_typed(self.raw, self.raw)

        with self.assertRaises(ValueError):
            self.build()

        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
