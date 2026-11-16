import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from streamlit.testing.v1 import AppTest
from src.alert_evaluation import evaluate_source, evaluate_database
from src.demo import COLUMNS


class AlertEvaluationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root/'matrix.db'
        with sqlite3.connect(self.database) as conn:
            conn.execute('CREATE TABLE transactions (is_fraud INTEGER, legacy_flag INTEGER)')
            conn.executemany('INSERT INTO transactions VALUES (?,?)',
                             [(1, 1)]*2+[(0, 1)]*1+[(1, 0)]*3+[(0, 0)]*4)

    def test_confusion_cells_and_rates_against_manual_counts(self):
        result = evaluate_database(self.database, source_kind='full')
        self.assertEqual(result['confusion_counts'], {
            'true_positives': 2, 'false_positives': 1,
            'false_negatives': 3, 'true_negatives': 4})
        self.assertEqual(result['total_records'], 10)
        self.assertAlmostEqual(result['metrics']['precision'], 2/3)
        self.assertAlmostEqual(result['metrics']['recall'], 2/5)
        self.assertAlmostEqual(result['metrics']['false_positive_rate'], 1/5)
        self.assertAlmostEqual(result['metrics']['alert_rate'], 3/10)

    def test_all_rows_evaluated_and_database_is_unchanged(self):
        with sqlite3.connect(self.database) as conn:
            conn.executemany('INSERT INTO transactions VALUES (?,?)', [(1, 0)]*300)
        before = self.database.read_bytes()
        result = evaluate_database(self.database, source_kind='full')
        self.assertEqual(result['total_records'], 310)
        self.assertEqual(result['confusion_counts']['false_negatives'], 303)
        self.assertEqual(self.database.read_bytes(), before)

    def test_undefined_denominators_are_null_not_zero(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute('DELETE FROM transactions')
        result = evaluate_database(self.database, source_kind='full')
        self.assertEqual(result['total_records'], 0)
        self.assertTrue(all(v is None for v in result['metrics'].values()))
        with sqlite3.connect(self.database) as conn:
            conn.execute('INSERT INTO transactions VALUES (1,0)')
        result = evaluate_database(self.database, source_kind='full')
        self.assertIsNone(result['metrics']['precision'])
        self.assertEqual(result['metrics']['recall'], 0)
        self.assertIsNone(result['metrics']['false_positive_rate'])

    def test_invalid_binary_fields_rejected(self):
        for label, flag in [(None, 0), (1, None), (2, 1), (0, -1), ('unknown', 0)]:
            with self.subTest(label=label, flag=flag):
                with sqlite3.connect(self.database) as conn:
                    conn.execute('DELETE FROM transactions')
                    conn.execute('INSERT INTO transactions VALUES (?,?)', (label, flag))
                with self.assertRaises(ValueError):
                    evaluate_database(self.database, source_kind='full')

    def test_missing_database_not_created_and_unknown_scope_rejected(self):
        missing = self.root/'absent.db'
        with self.assertRaises(FileNotFoundError):
            evaluate_source(missing, source_kind='full')
        self.assertFalse(missing.exists())
        with self.assertRaises(ValueError):
            evaluate_database(self.database, source_kind='production')

    def write_sample(self):
        path = self.root/'demo/transactions.json'
        path.parent.mkdir()
        rows = [[i+1, 1, 'TRANSFER', 100, 'A', 'B', label, flag]
                for i, (label, flag) in enumerate([(1, 1), (1, 0), (0, 1), (0, 0)])]
        path.write_text(json.dumps({'format_version': 1, 'columns': COLUMNS.split(','), 'rows': rows}))
        return path

    def test_demo_reuses_validation_and_source_is_preserved(self):
        sample = self.write_sample()
        before = sample.read_bytes()
        result = evaluate_source(sample, source_kind='demo')
        self.assertEqual(result['source_kind'], 'demo')
        self.assertIn('unsuitable for population', result['notice'])
        self.assertTrue(all(v == 1 for v in result['confusion_counts'].values()))
        self.assertEqual(sample.read_bytes(), before)
        payload = json.loads(sample.read_text())
        payload['rows'][0][-1] = 2
        sample.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            evaluate_source(sample, source_kind='demo')

    def test_committed_snapshot_and_cli_are_consistent(self):
        root = Path(__file__).resolve().parents[1]
        report = evaluate_source(root/'demo/transactions.json', source_kind='demo')
        self.assertEqual(report['confusion_counts'], {
            'true_positives': 16, 'false_positives': 0,
            'false_negatives': 100, 'true_negatives': 2463})
        proc = subprocess.run([sys.executable, '-m', 'src.alert_evaluation', '--source', 'demo'],
                              cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), report)

    def test_ui_evaluation_ignores_explorer_filters_and_clears_on_source_change(self):
        self.write_sample()
        missing = self.root/'data/fraud_typed.db'
        script = ('from pathlib import Path\nfrom unittest.mock import patch\n'
                  'from app import main\nwith patch("app.DEFAULT_DATABASE", Path('
                  + repr(str(missing)) + ')):\n    main()\n')
        app = AppTest.from_string(script).run()
        app.selectbox[1].select('1').run()  # A label filter must not change evaluation.
        app.button(key='evaluate_legacy').click().run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ['50.00%', '50.00%', '50.00%', '50.00%'])
        self.assertEqual(app.dataframe[0].value['Flag = 1 (alert)'].sum(), 2)
        app.radio[0].set_value('Full local database').run()
        self.assertFalse(app.metric)
        self.assertFalse(app.dataframe)
        app.button(key='evaluate_legacy').click().run()
        self.assertTrue(app.error)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
