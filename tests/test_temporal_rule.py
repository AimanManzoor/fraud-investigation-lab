import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from src.temporal_rule import select_threshold, evaluate_frozen


class TemporalRuleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root/'typed.db'
        with sqlite3.connect(self.database) as conn:
            conn.execute('CREATE TABLE transactions (step INTEGER, transaction_type TEXT, amount_minor INTEGER, is_fraud INTEGER, legacy_flag INTEGER)')
            conn.executemany('INSERT INTO transactions VALUES (?,?,?,?,?)', [
                (1, 'TRANSFER', 100, 1, 0), (1, 'TRANSFER', 80, 0, 1), (1, 'PAYMENT', 500, 0, 0),
                (2, 'TRANSFER', 200, 1, 0), (2, 'TRANSFER', 150, 0, 0),
                (3, 'TRANSFER', 200, 1, 1), (3, 'TRANSFER', 250, 0, 0),
                (3, 'TRANSFER', 50, 1, 0), (4, 'PAYMENT', 1000, 0, 0)])

    def select(self, **changes):
        args = {'cutoff_step': 2, 'max_alerts_per_step': 1, 'thresholds': ['0.50', '1.00', '2.00']}
        return select_threshold(self.database, **{**args, **changes})

    def test_capacity_feasibility_selects_without_splitting_steps(self):
        protocol = self.select()
        self.assertEqual(protocol['selected_threshold_minor'], 200)
        self.assertEqual(protocol['selection_steps'], [1, 2])
        self.assertEqual(protocol['held_out_steps'], [3, 4])
        self.assertEqual([s['selection']['total_records'] for s in protocol['selection_results']], [5, 5, 5])
        self.assertEqual([s['selection']['peak_alerts_per_step'] for s in protocol['selection_results']], [2, 2, 1])

    def test_frozen_holdout_counts_and_capacity_breach(self):
        report = evaluate_frozen(self.database, self.select())
        self.assertEqual(report['candidate']['confusion_counts'], {
            'true_positives': 1, 'false_positives': 1, 'false_negatives': 1, 'true_negatives': 1})
        self.assertEqual(report['candidate']['total_records'], 4)
        self.assertEqual(report['candidate']['peak_alerts_per_step'], 2)
        self.assertEqual(report['candidate']['steps_exceeding_capacity'], 1)
        self.assertEqual(report['legacy']['steps_exceeding_capacity'], 0)
        self.assertEqual(report['selected_threshold_minor'], 200)

    def test_recall_then_false_alerts_then_higher_threshold_tie_break(self):
        # At capacity 2, thresholds 50 and 100 catch two positives; 100 has fewer FP.
        self.assertEqual(self.select(max_alerts_per_step=2)['selected_threshold_minor'], 100)
        # 90 and 100 have identical decisions; the fixed final tie-break chooses 100.
        protocol = self.select(max_alerts_per_step=2, thresholds=['0.90', '1.00'])
        self.assertEqual(protocol['selected_threshold_minor'], 100)

    def test_changing_future_labels_does_not_change_selection(self):
        first = self.select()
        with sqlite3.connect(self.database) as conn:
            conn.execute('UPDATE transactions SET is_fraud=1-is_fraud WHERE step>2')
        second = self.select()
        self.assertEqual(first['selection_results'], second['selection_results'])
        self.assertEqual(first['selected_threshold_minor'], second['selected_threshold_minor'])

    def test_selection_does_not_validate_or_query_future_labels(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute('UPDATE transactions SET is_fraud=99 WHERE step>2')
        protocol = self.select()
        self.assertEqual(protocol['status'], 'threshold_selected')
        with self.assertRaises(ValueError):
            evaluate_frozen(self.database, protocol)

    def test_no_feasible_threshold_does_not_fall_back(self):
        protocol = self.select(max_alerts_per_step=0)
        self.assertEqual(protocol['status'], 'no_feasible_threshold')
        self.assertIsNone(protocol['selected_threshold_minor'])
        with self.assertRaises(ValueError):
            evaluate_frozen(self.database, protocol)

    def test_no_selection_positive_labels_does_not_optimize_undefined_recall(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute('UPDATE transactions SET is_fraud=0 WHERE step<=2')
        protocol = self.select()
        self.assertEqual(protocol['status'], 'insufficient_selection_labels')
        self.assertIsNone(protocol['selected_threshold_minor'])

    def test_bad_protocol_source_or_modified_source_is_rejected(self):
        protocol = self.select()
        modified = copy.deepcopy(protocol)
        modified['selected_threshold_minor'] = 50
        with self.assertRaises(ValueError):
            evaluate_frozen(self.database, modified)
        with sqlite3.connect(self.database) as conn:
            conn.execute('INSERT INTO transactions VALUES (5,"TRANSFER",200,1,0)')
        with self.assertRaises(ValueError):
            evaluate_frozen(self.database, protocol)

    def test_invalid_protocol_parameters_and_demo_are_rejected(self):
        for changes in [{'cutoff_step': True}, {'cutoff_step': 4}, {'cutoff_step': 0},
                        {'max_alerts_per_step': -1}, {'max_alerts_per_step': 1.5},
                        {'thresholds': []}, {'thresholds': ['1', '1.00']},
                        {'thresholds': ['0.001']}, {'thresholds': ['NaN']},
                        {'thresholds': ['1']*11}, {'source_kind': 'demo'}]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.select(**changes)

    def test_bad_source_steps_or_selection_features_are_rejected(self):
        for field, value in [('step', None), ('step', 1.5), ('step', -1),
                             ('amount_minor', -1), ('transaction_type', 'UNKNOWN')]:
            with self.subTest(field=field, value=value):
                with sqlite3.connect(self.database) as conn:
                    conn.execute('UPDATE transactions SET '+field+'=? WHERE rowid=1', (value,))
                with self.assertRaises(ValueError):
                    self.select()
                with sqlite3.connect(self.database) as conn:
                    conn.execute('UPDATE transactions SET step=1,amount_minor=100,transaction_type="TRANSFER" WHERE rowid=1')

    def test_missing_database_is_not_created(self):
        self.database.unlink()
        with self.assertRaises(FileNotFoundError):
            self.select()
        self.assertFalse(self.database.exists())

    def test_wal_source_is_rejected(self):
        with sqlite3.connect(self.database) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            with self.assertRaises(ValueError):
                self.select()

    def test_selection_and_evaluation_preserve_database_bytes(self):
        before = self.database.read_bytes()
        protocol = self.select()
        evaluate_frozen(self.database, protocol)
        self.assertEqual(before, self.database.read_bytes())

    def test_separate_cli_stages_json_and_exclusive_outputs(self):
        root = Path(__file__).resolve().parents[1]
        selection, output = self.root/'selection.json', self.root/'test.json'
        base = [sys.executable, '-m', 'src.temporal_rule', '--database', str(self.database)]
        proc = subprocess.run(base+['select', '--cutoff-step', '2', '--max-alerts-per-step', '1',
                                   '--thresholds', '0.50,1.00,2.00', '--output', str(selection)],
                              cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        saved = json.loads(selection.read_text())
        self.assertNotIn('candidate', saved)
        proc = subprocess.run(base+['evaluate', '--selection', str(selection), '--output', str(output)],
                              cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['candidate']['total_records'], 4)
        before = output.read_bytes()
        proc = subprocess.run(base+['evaluate', '--selection', str(selection), '--output', str(output)],
                              cwd=root, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
