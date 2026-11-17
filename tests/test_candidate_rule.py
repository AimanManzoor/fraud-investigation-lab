import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from streamlit.testing.v1 import AppTest
from src.alert_evaluation import evaluate_database
from src.candidate_rule import candidate_alert, compare_database, compare_source


class CandidateRuleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name)/'typed.db'
        with sqlite3.connect(self.database) as conn:
            conn.execute('CREATE TABLE transactions (transaction_type TEXT, amount_minor INTEGER, is_fraud INTEGER, legacy_flag INTEGER)')
            conn.executemany('INSERT INTO transactions VALUES (?,?,?,?)', [
                ('TRANSFER', 9999, 1, 1), ('TRANSFER', 10000, 1, 1),
                ('TRANSFER', 10001, 0, 0), ('PAYMENT', 10001, 1, 0),
                ('TRANSFER', 0, 0, 0), ('CASH_OUT', 1000000, 0, 0)])

    def test_rule_positive_negative_boundary_and_invalid_inputs(self):
        for kind, amount, expected in [('TRANSFER', 9999, False), ('TRANSFER', 10000, True),
                                       ('TRANSFER', 10001, True), ('PAYMENT', 10001, False),
                                       ('CASH_OUT', 1000000, False)]:
            self.assertEqual(candidate_alert(kind, amount, 10000), expected)
        for kind, amount, threshold in [('UNKNOWN', 100, 100), ('TRANSFER', True, 100),
                                        ('TRANSFER', -1, 100), ('TRANSFER', 1.1, 100),
                                        ('TRANSFER', 100, True), ('TRANSFER', 100, 2**63)]:
            with self.assertRaises(ValueError):
                candidate_alert(kind, amount, threshold)

    def test_manual_confusion_counts_and_legacy_parity(self):
        comparison = compare_database(self.database, source_kind='full', threshold='100.00')
        self.assertEqual(comparison['candidate']['confusion_counts'], {
            'true_positives': 1, 'false_positives': 1, 'false_negatives': 2, 'true_negatives': 2})
        self.assertEqual(comparison['legacy']['confusion_counts'], {
            'true_positives': 2, 'false_positives': 0, 'false_negatives': 1, 'true_negatives': 3})
        self.assertEqual(comparison['legacy'], evaluate_database(self.database, source_kind='full'))
        self.assertAlmostEqual(comparison['candidate']['metrics']['recall'], 1/3)
        self.assertEqual(comparison['candidate']['metrics']['precision'], 0.5)
        self.assertEqual(comparison['rule']['threshold_minor'], 10000)

    def test_labels_and_legacy_flags_do_not_change_candidate_alerts(self):
        first = compare_database(self.database, source_kind='full', threshold='100')
        with sqlite3.connect(self.database) as conn:
            conn.execute('UPDATE transactions SET is_fraud=1-is_fraud, legacy_flag=1-legacy_flag')
        second = compare_database(self.database, source_kind='full', threshold='100')
        self.assertEqual(first['candidate']['flagged_records'], second['candidate']['flagged_records'])
        self.assertEqual(second['rule']['inputs'], ['transaction_type', 'amount_minor'])

    def test_all_rows_evaluated_without_changing_source(self):
        with sqlite3.connect(self.database) as conn:
            conn.executemany('INSERT INTO transactions VALUES (?,?,?,?)', [('TRANSFER', 10000, 1, 0)]*300)
        before = self.database.read_bytes()
        comparison = compare_database(self.database, source_kind='full', threshold='100')
        self.assertEqual(comparison['total_records'], 306)
        self.assertEqual(comparison['candidate']['confusion_counts']['true_positives'], 301)
        self.assertEqual(before, self.database.read_bytes())

    def test_bad_threshold_missing_source_and_bad_scope_are_rejected(self):
        for threshold in ['0.001', '-1', 'NaN', 'Infinity', '100 OR 1=1', True]:
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    compare_database(self.database, source_kind='full', threshold=threshold)
        missing = self.database.with_name('missing.db')
        with self.assertRaises(FileNotFoundError):
            compare_source(missing, source_kind='full')
        self.assertFalse(missing.exists())
        with self.assertRaises(ValueError):
            compare_source(self.database, source_kind='production')

    def test_invalid_source_fields_fail_instead_of_becoming_negative_alerts(self):
        for kind, amount, label, legacy in [('UNKNOWN', 100, 0, 0), (None, 100, 0, 0),
                                            ('TRANSFER', None, 0, 0), ('TRANSFER', -1, 0, 0),
                                            ('TRANSFER', 1.5, 0, 0), ('TRANSFER', 100, None, 0),
                                            ('TRANSFER', 100, 0, 2)]:
            with self.subTest(kind=kind, amount=amount, label=label, legacy=legacy):
                with sqlite3.connect(self.database) as conn:
                    conn.execute('DELETE FROM transactions')
                    conn.execute('INSERT INTO transactions VALUES (?,?,?,?)', (kind, amount, label, legacy))
                with self.assertRaises(ValueError):
                    compare_database(self.database, source_kind='full')

    def test_empty_source_has_zero_counts_and_undefined_rates(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute('DELETE FROM transactions')
        report = compare_database(self.database, source_kind='full')
        self.assertEqual(report['total_records'], 0)
        for method in ['legacy', 'candidate']:
            self.assertTrue(all(v is None for v in report[method]['metrics'].values()))

    def test_committed_demo_counts_and_cli(self):
        root = Path(__file__).resolve().parents[1]
        sample = root/'demo/transactions.json'
        before = sample.read_bytes()
        comparison = compare_source(sample, source_kind='demo')
        self.assertEqual(comparison['candidate']['confusion_counts'], {
            'true_positives': 31, 'false_positives': 255, 'false_negatives': 85, 'true_negatives': 2208})
        self.assertEqual(comparison['legacy']['flagged_records'], 16)
        self.assertIn('unsuitable for population', comparison['notice'])
        self.assertEqual(before, sample.read_bytes())
        proc = subprocess.run([sys.executable, '-m', 'src.candidate_rule', '--source', 'demo'],
                              cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), comparison)


class CandidateAppTests(unittest.TestCase):
    def setUp(self):
        from tests.test_explorer import ExplorerTests
        fixture = ExplorerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.database = fixture.database

    def test_comparison_ignores_filters_and_hides_when_threshold_changes(self):
        app = AppTest.from_string('from app import main\nmain('+repr(str(self.database))+')').run()
        app.selectbox[1].select('1').run()
        app.text_input(key='rule_threshold').set_value('2.00').run()
        app.button(key='compare_candidate').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(list(app.dataframe[0].value['Alerts']), [2, 1])
        self.assertEqual(list(app.dataframe[0].value['true_positives']), [1, 0])
        app.text_input(key='rule_threshold').set_value('0.001').run()
        self.assertFalse(app.dataframe)
        app.button(key='compare_candidate').click().run()
        self.assertTrue(app.error)
        self.assertFalse(app.dataframe)

    def test_source_switch_clears_comparison_and_missing_source_is_not_created(self):
        from src.demo import COLUMNS
        root = self.database.parent
        sample = root/'demo/transactions.json'
        sample.parent.mkdir()
        sample.write_text(json.dumps({'format_version': 1, 'columns': COLUMNS.split(','),
                                     'rows': [[1, 1, 'TRANSFER', 10000, 'A', 'B', 1, 0]]}))
        missing = root/'data/fraud_typed.db'
        script = ('from pathlib import Path\nfrom unittest.mock import patch\nfrom app import main\n'
                  'with patch("app.DEFAULT_DATABASE", Path('+repr(str(missing))+')):\n    main()\n')
        app = AppTest.from_string(script).run()
        app.button(key='compare_candidate').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.dataframe)
        app.radio[0].set_value('Full local database').run()
        self.assertFalse(app.dataframe)
        app.button(key='compare_candidate').click().run()
        self.assertTrue(app.error)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
