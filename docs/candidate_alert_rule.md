# Experimental candidate alert rule

## Rule and intended use

`transfer_amount_v1` proposes a review alert when:

1. transaction_type is exactly TRANSFER; and
2. amount_minor is greater than or equal to the selected threshold in exact
   scale-100 integer units.

The default threshold is 200,000.00 dataset units (20,000,000 minor units).
It is a manual experimental choice, not a fitted, optimized, recommended or
validated operating threshold. No currency is assumed. A review alert is not
a fraud verdict and does not trigger any action on an account.

Only transaction type and amount determine the candidate alert. Fraud labels,
legacy flags, balances and future account history are not rule inputs. The
legacy flag and synthetic fraud label are read separately for evaluation.

## Implementation and comparison

`src/candidate_rule.py` defines a Python reference predicate and a parameterized
SQL CASE expression for aggregate evaluation. Tests check positive, negative,
and exact-boundary cases. Invalid types, amounts, labels, flags, or unsupported
threshold precision stop the comparison rather than silently counting a
negative alert.

Both candidate and legacy confusion counts are computed in one grouped query
within one read-only SQLite snapshot, covering every row in the selected
source. Explorer filters and the first-200 display limit do not apply. The
shared metric formatter is reused from `src/alert_evaluation.py` so both methods
use the same definitions and zero-denominator behavior.

Undefined rates are JSON null / UI N/A. Empty valid tables yield zero counts
and undefined rates. Missing sources are not created; original data and flags
are never overwritten. There is no model training, provider call, automatic
threshold selection or query timeout.

## Observed demo comparison at the default threshold

| Sample measure | Candidate | Recorded legacy flag |
|---|---:|---:|
| Alerts | 286 | 16 |
| True positives | 31 | 16 |
| False positives | 255 | 0 |
| False negatives | 85 | 100 |
| True negatives | 2,208 | 2,463 |
| Precision | 10.84% | 100% |
| Recall | 26.72% | 13.79% |

These are observed counts and rates within the committed 2,579-record curated
demo. Its selection deliberately enriches labeled and flagged cases. They are
not population estimates, held-out results, or evidence that either method
generalizes. The candidate finds more labeled cases here at the cost of many
more false alerts; this does not establish a superior rule. No new full-dataset
comparison or review-cost study was performed in this milestone.

Trying thresholds against these same labels is exploratory analysis. A future
threshold-selection experiment must separate selection data from final test
data and preserve time-step boundaries. Do not choose a best threshold from
this enriched demo and report it as validated performance.

## Use it

In Streamlit, expand **Compare an experimental alert rule**, enter the threshold,
and click **Compare candidate and legacy**. Download the JSON report to retain
the rule version, threshold, scope, confusion counts and rates. Changing the
source or threshold hides old comparisons until a new comparison is submitted.

```bash
.venv/bin/python -m src.candidate_rule --source demo --threshold 200000.00
.venv/bin/python -m unittest discover -s tests -t . -v
```

Use `--source full` only with the existing local typed database. Demo mode
reuses the same validated temporary SQLite loader as the explorer. The CLI
prints JSON and exits nonzero on handled source/input errors.

## Validation and next work

Ten added test methods bring the suite to 83 tests. Checks cover independent
confusion counts and ratios, exact amount boundaries, invalid source data,
label/legacy changes that must not affect candidate alert counts, more than
200 rows, read-only behavior, committed demo counts, CLI JSON, threshold
invalidation, ignored explorer filters and source switching.

Next: specify analyst review capacity and false-alert/missed-case costs, then
design a chronological threshold-selection and held-out evaluation experiment.
Record the protocol before looking at final test results. Keep this rule as a
transparent baseline when later comparing models.
