"""Separate earlier-period threshold selection from frozen later-period evaluation."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from src.alert_evaluation import summarize_counts
from src.explorer import TYPES, format_amount
from src.money import MAX_INTEGER, to_minor_units

DEFAULT_THRESHOLDS = ('100000', '200000', '500000', '1000000', '2000000')
COUNTS = ('true_positives', 'false_positives', 'false_negatives', 'true_negatives')
CELLS = {(1, 1): COUNTS[0], (0, 1): COUNTS[1], (1, 0): COUNTS[2], (0, 0): COUNTS[3]}


def _positive_integer(value, name, *, allow_zero=False):
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= MAX_INTEGER:
        raise ValueError(f'{name} must be an integer in the supported range.')


def _identity(path):
    stat = path.stat()
    return {'path': str(path.resolve()), 'size_bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def _digest(protocol):
    value = {k: v for k, v in protocol.items() if k != 'protocol_sha256'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _steps(conn):
    counts = {}
    for step, n in conn.execute('SELECT step, COUNT(*) FROM transactions GROUP BY step'):
        _positive_integer(step, 'Source step')
        counts[step] = n
    if not counts:
        raise ValueError('The source has no records.')
    return counts


def _require_static_source(conn):
    if conn.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal':
        raise ValueError('Use a static non-WAL copy of the typed source for this protocol.')


def _measure(conn, cutoff, threshold, *, later=False, legacy=False, capacity=None):
    # Only the chosen side of the time boundary contributes labels or alerts.
    where = 'step > ?' if later else 'step <= ?'
    flag = 'legacy_flag' if legacy else "CASE WHEN transaction_type='TRANSFER' AND amount_minor>=? THEN 1 ELSE 0 END"
    params = [] if legacy else [threshold]
    params += [*TYPES, cutoff]
    query = (
        'SELECT step,is_fraud,'+flag+' AS alert,COUNT(*), '
        "SUM(CASE WHEN typeof(amount_minor)!='integer' OR amount_minor<0 "
        "OR typeof(transaction_type)!='text' OR transaction_type NOT IN (?,?,?,?,?) "
        'THEN 1 ELSE 0 END) FROM transactions WHERE '+where+' GROUP BY step,is_fraud,alert'
    )
    counts, alerts_by_step, rows_by_step = dict.fromkeys(COUNTS, 0), {}, {}
    for step, label, alert, n, invalid in conn.execute(query, params):
        if (invalid or type(label) is not int or label not in (0, 1) or
                type(alert) is not int or alert not in (0, 1)):
            raise ValueError('Period contains invalid types, amounts, labels or flags.')
        counts[CELLS[label, alert]] += n
        alerts_by_step[step] = alerts_by_step.get(step, 0)+alert*n
        rows_by_step[step] = rows_by_step.get(step, 0)+n
    summary = summarize_counts(counts, source_kind='full', evaluation='temporal_rule_period')
    summary['scope'] = 'later steps only' if later else 'earlier selection steps only'
    summary['notice'] = 'This period of the selected local synthetic source only; not production performance.'
    summary['observed_steps'] = len(rows_by_step)
    summary['peak_alerts_per_step'] = max(alerts_by_step.values(), default=0)
    summary['steps_exceeding_capacity'] = (sum(n > capacity for n in alerts_by_step.values())
                                           if capacity is not None else None)
    return summary


def select_threshold(database, *, cutoff_step, max_alerts_per_step,
                     thresholds=DEFAULT_THRESHOLDS, source_kind='full'):
    if source_kind != 'full':
        raise ValueError('The enriched demo is not supported for threshold selection.')
    _positive_integer(cutoff_step, 'Cutoff step')
    _positive_integer(max_alerts_per_step, 'Review capacity', allow_zero=True)
    if not isinstance(thresholds, (list, tuple)) or not 1 <= len(thresholds) <= 10:
        raise ValueError('Supply 1 to 10 prespecified threshold strings.')
    candidates = [to_minor_units(raw) for raw in thresholds]
    if len(set(candidates)) != len(candidates):
        raise ValueError('Candidate thresholds must be distinct exact values.')
    candidates.sort()
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError('Full local typed database is missing.')
    identity = _identity(path)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as conn:
        _require_static_source(conn)
        conn.execute('BEGIN')
        steps = _steps(conn)  # Source time/count metadata only; no later labels.
        earlier = [s for s in steps if s <= cutoff_step]
        later = [s for s in steps if s > cutoff_step]
        if not earlier or not later:
            raise ValueError('Both sides of the cutoff must contain complete time steps.')
        scores = [{'threshold_minor': threshold,
                   'selection': _measure(conn, cutoff_step, threshold, capacity=max_alerts_per_step)}
                  for threshold in candidates]
    if _identity(path) != identity:
        raise ValueError('Source changed during selection.')
    feasible = [score for score in scores
                if score['selection']['peak_alerts_per_step'] <= max_alerts_per_step]
    status, selected = 'no_feasible_threshold', None
    if not scores[0]['selection']['labeled_fraud_records']:
        status = 'insufficient_selection_labels'
    elif feasible:
        # Same selection labels for each candidate: max TP also maximizes recall.
        winner = max(feasible, key=lambda score: (
            score['selection']['confusion_counts']['true_positives'],
            -score['selection']['confusion_counts']['false_positives'], score['threshold_minor']))
        selected, status = winner['threshold_minor'], 'threshold_selected'
    protocol = {'protocol_version': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'status': status, 'source_kind': 'full_local_synthetic', 'source_identity': identity,
                'cutoff_step': cutoff_step, 'max_alerts_per_step': max_alerts_per_step,
                'selection_steps': sorted(earlier), 'held_out_steps': sorted(later),
                'candidate_thresholds_minor': candidates, 'selection_results': scores,
                'selected_threshold_minor': selected, 'model_calls': 0,
                'policy': 'Among capacity-feasible candidates: max TP, then min FP, then higher threshold.',
                'holdout_policy': 'Step <= cutoff selects; step > cutoff is evaluated only by a separate command.'}
    protocol['protocol_sha256'] = _digest(protocol)
    return protocol


def evaluate_frozen(database, protocol):
    if (not isinstance(protocol, dict) or protocol.get('protocol_version') != 1 or
            protocol.get('status') != 'threshold_selected' or protocol.get('source_kind') != 'full_local_synthetic' or
            protocol.get('protocol_sha256') != _digest(protocol)):
        raise ValueError('A valid saved selection protocol is required.')
    cutoff = protocol['cutoff_step']
    capacity = protocol['max_alerts_per_step']
    selected = protocol['selected_threshold_minor']
    _positive_integer(cutoff, 'Cutoff step')
    _positive_integer(capacity, 'Review capacity', allow_zero=True)
    _positive_integer(selected, 'Frozen threshold', allow_zero=True)
    if selected not in protocol['candidate_thresholds_minor']:
        raise ValueError('Frozen threshold is not a protocol candidate.')
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError('Full local typed database is missing.')
    identity = _identity(path)
    if identity != protocol['source_identity']:
        raise ValueError('The source differs from the saved selection source.')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as conn:
        _require_static_source(conn)
        conn.execute('BEGIN')
        candidate = _measure(conn, cutoff, selected, later=True, capacity=capacity)
        legacy = _measure(conn, cutoff, selected, later=True, legacy=True, capacity=capacity)
    if _identity(path) != identity:
        raise ValueError('Source changed during evaluation.')
    return {'evaluation': 'frozen_later_period_rule_evaluation', 'protocol_sha256': protocol['protocol_sha256'],
            'cutoff_step': cutoff, 'selected_threshold_minor': selected,
            'selected_threshold_display': format_amount(selected), 'max_alerts_per_step': capacity,
            'candidate': candidate, 'legacy': legacy, 'model_calls': 0,
            'notice': 'Synthetic local source only. Selection-period capacity does not guarantee later capacity or generalization. Repeated tuning after inspecting this holdout invalidates its role as a final test.'}


def _save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default=str(Path(__file__).resolve().parents[1]/'data/fraud_typed.db'))
    commands = parser.add_subparsers(dest='action', required=True)
    select = commands.add_parser('select')
    select.add_argument('--cutoff-step', type=int, required=True)
    select.add_argument('--max-alerts-per-step', type=int, required=True)
    select.add_argument('--thresholds', default=','.join(DEFAULT_THRESHOLDS))
    select.add_argument('--output', required=True)
    evaluate = commands.add_parser('evaluate')
    evaluate.add_argument('--selection', required=True)
    evaluate.add_argument('--output', required=True)
    args = parser.parse_args()
    database = Path(args.database)
    try:
        if Path(args.output).exists():
            raise FileExistsError('Choose a new output path; existing reports are preserved.')
        if args.action == 'select':
            report = select_threshold(database, cutoff_step=args.cutoff_step,
                                      max_alerts_per_step=args.max_alerts_per_step,
                                      thresholds=args.thresholds.split(','))
        else:
            protocol = json.loads(Path(args.selection).read_text())
            report = evaluate_frozen(database, protocol)
        _save_new(args.output, report)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as exc:
        parser.exit(1, f'Temporal evaluation stopped: {type(exc).__name__}\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
