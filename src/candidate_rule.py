"""Experimental TRANSFER + amount rule, compared with a recorded legacy flag."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from src.alert_evaluation import summarize_counts
from src.demo import demo_database
from src.explorer import TYPES, format_amount
from src.money import MAX_INTEGER, to_minor_units

DEFAULT_THRESHOLD = '200000.00'


def candidate_alert(transaction_type, amount_minor, threshold_minor):
    if transaction_type not in TYPES:
        raise ValueError('Unknown transaction type.')
    if any(type(v) is not int or not 0 <= v <= MAX_INTEGER
           for v in (amount_minor, threshold_minor)):
        raise ValueError('Amounts and thresholds must be exact non-negative integer minor units.')
    return transaction_type == 'TRANSFER' and amount_minor >= threshold_minor


def compare_database(database, *, source_kind, threshold=DEFAULT_THRESHOLD):
    if source_kind not in {'demo', 'full'}:
        raise ValueError('Source must be demo or full.')
    minimum = to_minor_units(threshold)
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError('Typed database missing: data/fraud_typed.db')
    empty = {'true_positives': 0, 'false_positives': 0, 'false_negatives': 0, 'true_negatives': 0}
    legacy_counts, candidate_counts = dict(empty), dict(empty)
    cells = {(1, 1): 'true_positives', (0, 1): 'false_positives',
             (1, 0): 'false_negatives', (0, 0): 'true_negatives'}
    # One snapshot and grouped query; parameters never enter SQL source text.
    sql = (
        "SELECT is_fraud, legacy_flag, "
        "CASE WHEN transaction_type='TRANSFER' AND amount_minor>=? THEN 1 ELSE 0 END AS candidate, "
        "COUNT(*), SUM(CASE WHEN typeof(amount_minor)!='integer' OR amount_minor<0 "
        "OR typeof(transaction_type)!='text' OR transaction_type NOT IN (?,?,?,?,?) "
        "THEN 1 ELSE 0 END) FROM transactions GROUP BY is_fraud, legacy_flag, candidate"
    )
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as conn:
        conn.execute('BEGIN')
        for label, legacy, candidate, count, invalid in conn.execute(sql, [minimum, *TYPES]):
            if (invalid or type(label) is not int or type(legacy) is not int or
                    label not in (0, 1) or legacy not in (0, 1)):
                raise ValueError('Comparison requires valid types, amounts, and complete binary labels/flags.')
            legacy_counts[cells[label, legacy]] += count
            candidate_counts[cells[label, candidate]] += count
    legacy = summarize_counts(legacy_counts, source_kind=source_kind)
    candidate = summarize_counts(candidate_counts, source_kind=source_kind,
                                 evaluation='experimental_candidate_vs_synthetic_labels')
    return {'comparison': 'transfer_amount_v1_vs_recorded_legacy_flag',
            'source_kind': source_kind, 'synthetic_data': True,
            'scope': candidate['scope'], 'total_records': candidate['total_records'],
            'rule': {'id': 'transfer_amount_v1', 'transaction_type': 'TRANSFER',
                     'operator': '>=', 'threshold_minor': minimum,
                     'threshold_display': format_amount(minimum), 'amount_scale': 100,
                     'inputs': ['transaction_type', 'amount_minor'],
                     'selection_status': 'manual experimental threshold; not fitted or validated'},
            'candidate': candidate, 'legacy': legacy, 'notice': candidate['notice'],
            'model_calls': 0}


def compare_source(source, *, source_kind, threshold=DEFAULT_THRESHOLD):
    to_minor_units(threshold)  # Reject bad thresholds before creating a disposable demo DB.
    if source_kind == 'demo':
        with demo_database(source) as database:
            return compare_database(database, source_kind='demo', threshold=threshold)
    return compare_database(source, source_kind=source_kind, threshold=threshold)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('demo', 'full'), default='demo')
    parser.add_argument('--threshold', default=DEFAULT_THRESHOLD,
                        help='Raw amount text in dataset units, exactly representable at scale 100.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = root/('demo/transactions.json' if args.source == 'demo' else 'data/fraud_typed.db')
    try:
        result = compare_source(path, source_kind=args.source, threshold=args.threshold)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'Rule comparison stopped: {type(exc).__name__}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
