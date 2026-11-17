"""Evaluate the recorded legacy flag against synthetic labels; no new predictions."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from src.demo import demo_database


def _rate(numerator, denominator):
    return numerator/denominator if denominator else None


def evaluate_database(database, *, source_kind):
    if source_kind not in {'demo', 'full'}:
        raise ValueError('Source must be demo or full.')
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError('Typed database missing: data/fraud_typed.db')
    counts = {'true_positives': 0, 'false_positives': 0,
              'false_negatives': 0, 'true_negatives': 0}
    cells = {(1, 1): 'true_positives', (0, 1): 'false_positives',
             (1, 0): 'false_negatives', (0, 0): 'true_negatives'}
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as conn:
        conn.execute('BEGIN')
        for label, flag, count in conn.execute(
                'SELECT is_fraud, legacy_flag, COUNT(*) FROM transactions '
                'GROUP BY is_fraud, legacy_flag'):
            if (type(label) is not int or type(flag) is not int or
                    label not in (0, 1) or flag not in (0, 1)):
                raise ValueError('Evaluation requires complete binary labels and flags.')
            counts[cells[label, flag]] += count
    return summarize_counts(counts, source_kind=source_kind)


def summarize_counts(counts, *, source_kind, evaluation='recorded_legacy_flag_vs_synthetic_labels'):
    tp, fp, fn, tn = (counts[k] for k in
                      ('true_positives', 'false_positives', 'false_negatives', 'true_negatives'))
    total = tp+fp+fn+tn
    return {'evaluation': evaluation,
            'source_kind': source_kind, 'synthetic_data': True,
            'scope': 'entire selected source; explorer filters and display limits do not apply',
            'total_records': total, 'labeled_fraud_records': tp+fn,
            'flagged_records': tp+fp, 'confusion_counts': counts,
            'metrics': {'precision': _rate(tp, tp+fp), 'recall': _rate(tp, tp+fn),
                        'false_positive_rate': _rate(fp, fp+tn),
                        'alert_rate': _rate(tp+fp, total)},
            'notice': ('Curated demo only: label and flag enrichment makes these sample metrics '
                       'unsuitable for population or full-dataset performance estimates.' if source_kind == 'demo'
                       else 'Full selected local synthetic dataset only; not production performance.'),
            'model_calls': 0}


def evaluate_source(source, *, source_kind):
    if source_kind == 'demo':
        with demo_database(source) as database:
            return evaluate_database(database, source_kind='demo')
    return evaluate_database(source, source_kind=source_kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('demo', 'full'), default='demo')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root/('demo/transactions.json' if args.source == 'demo' else 'data/fraud_typed.db')
    try:
        report = evaluate_source(source, source_kind=args.source)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'Evaluation stopped: {type(exc).__name__}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
