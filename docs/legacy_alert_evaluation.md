# Recorded legacy-flag evaluation

## What is evaluated

The evaluator compares the existing `legacy_flag` field with the synthetic
`is_fraud` dataset label. It does not generate alerts, train a model, choose a
threshold, or establish causal or production fraud-detection performance.
Labels and flags remain excluded from model-facing investigation evidence.

`src/alert_evaluation.py` uses one read-only SQLite grouped-count query over
the entire selected source. No explorer filter or display limit applies.
Demo mode reuses `src/demo.py` validation and disposable database setup;
full mode reads the existing local typed database. Sources are not modified.
Full-source evaluation scans records and has no implemented query timeout.

## Definitions

| Count | Synthetic label | Recorded flag |
|---|---:|---:|
| True positive (TP) | 1 | 1 |
| False positive (FP) | 0 | 1 |
| False negative (FN) | 1 | 0 |
| True negative (TN) | 0 | 0 |

- Precision = TP / (TP + FP): fraction of alerts with fraud labels.
- Recall = TP / (TP + FN): fraction of fraud-labeled records flagged.
- False-positive rate = FP / (FP + TN): fraction of non-fraud-labeled records flagged.
- Alert rate = (TP + FP) / total: fraction of selected-source records flagged.

If a denominator is zero, the JSON value is `null` and the dashboard shows
`N/A`. A missing source, schema error, or invalid/null label is an error, not
a zero-valued evaluation. Empty valid tables return zero counts and null rates.

## Observed committed-demo result

| Measure | Result |
|---|---:|
| Records | 2,579 |
| Fraud labels | 116 |
| Flags | 16 |
| TP / FP / FN / TN | 16 / 0 / 100 / 2,463 |
| Precision | 100% |
| Recall | 13.79% |
| False-positive rate | 0% |
| Alert rate | 0.62% |

The demo intentionally includes additional labeled and flagged cases. These
sample-specific rates are not estimates of population or full-dataset rates.
Even a 100% observed precision does not prove a generally reliable alerting
method. No new full-dataset evaluation was performed for this milestone.

## Run it

```bash
.venv/bin/python -m src.alert_evaluation --source demo
```

For the full local typed database, use `--source full`. No full database or
raw CSV is uploaded to GitHub or supplied to the hosted app. The CLI prints
JSON to stdout and exits nonzero on a handled source/validation error.

In Streamlit, expand **Evaluate the recorded legacy alert flag**, then click
**Evaluate selected source**. It works independently of Apply filters. Download
the JSON report to retain its source scope, counts, rates and limitations.
Switching sources or changing the source modification time clears previous
evaluation results. Changing explorer filters does not change this whole-source
evaluation, which is labeled explicitly in the interface.

## Tests and next steps

Eight added tests bring the suite to 73. They cover independently specified
confusion counts, formulas, undefined rates, more than 200 rows, source
preservation, invalid labels, missing sources, demo validation, the committed
snapshot and CLI, and UI scope/source-switch behavior. They make no AI calls.
Existing exploration and harness regression checks continue to pass.

Next: define one transparent candidate alert rule using pre-decision inputs,
write independent positive/negative/boundary cases, and evaluate it separately
from the legacy flag. Threshold selection and final evaluation must use
separate data; the enriched demo is not a suitable performance benchmark.
