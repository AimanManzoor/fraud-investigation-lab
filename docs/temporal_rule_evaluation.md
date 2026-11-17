# Chronological threshold selection and frozen later evaluation

## Purpose and status

This protocol adds a disciplined experiment for the existing experimental
TRANSFER + amount rule. It is implemented in `src/temporal_rule.py` and tested
on small independently specified SQLite fixtures. No new full-PaySim run was
performed and no operating threshold is recommended by this milestone.

The public enriched demo is not supported for threshold selection. The protocol
is a local CLI workflow over a declared full synthetic typed source, not a
hosted-app action. Declaring a source full is not authentication of its origin;
the caller must supply the intended un-enriched source.

## Prespecify the experiment

Before running selection, choose:

- A cutoff simulation step. Step <= cutoff is selection; step > cutoff is held out.
- A maximum number of review alerts per observed simulation step (hour).
- A fixed list of 1 to 10 distinct exact amount thresholds. The supplied defaults
  are 100000, 200000, 500000, 1000000, 2000000 dataset units. They are experimental,
  not optimized values.

No time step is split across periods, even when it contains many records. Both
periods must contain records. The cutoff is chosen by the caller, not tuned from
later labels. Time-step/count metadata across the source is inspected to validate
the boundary; later-period labels are not queried during selection.

There is no separate model-fitting period because this experiment fits no model
or preprocessing. A future ML comparison needs its own training/validation/test
protocol and past-only features.

## Selection rule

Each candidate is evaluated only on step <= cutoff. A threshold is feasible if
its **peak alerts in any observed selection step** does not exceed capacity.
The selection order is fixed:

1. Among feasible candidates, maximize true positives (equivalently recall on
   this common selection period).
2. Break ties with fewer false positives.
3. Break remaining ties with the higher amount threshold.

There is no automatic fallback when none is feasible. Selection returns
`no_feasible_threshold`. If selection contains no positive labels, it returns
`insufficient_selection_labels` rather than optimizing undefined recall.
Neither status can proceed to frozen evaluation.

The selection report contains the inputs, candidate results, chosen threshold
if any, exact step sets, source identity, timestamp and a protocol checksum.
It contains no held-out confusion counts or held-out label totals.

## Run the two stages separately

The following cutoff and capacity are **illustrative**, not recommendations.
Choose your protocol before seeing later results. Run from the repository root
after building the full `data/fraud_typed.db`:

```bash
.venv/bin/python -m src.temporal_rule select --cutoff-step 500 --max-alerts-per-step 20 --output reports/generated/selection_v1.json
```

Inspect the saved selection report. Only if its status is `threshold_selected`,
run the separate later-period command:

```bash
.venv/bin/python -m src.temporal_rule evaluate --selection reports/generated/selection_v1.json --output reports/generated/heldout_v1.json
```

To prespecify another grid, supply e.g. `--thresholds 100000,200000,500000` in the
selection command. To use another static typed SQLite file, put
`--database /absolute/path/typed.db` before `select` or `evaluate`.

Existing output files are not overwritten. Generated files stay under the
ignored reports directory and contain a local source path. Keep them local.
Nothing here changes the public demo's default threshold or writes source data.

## Frozen evaluation

The second command checks the saved protocol checksum, chosen candidate, and
source identity. It does not reselect or retune. It evaluates the frozen candidate
and the recorded legacy flag only on step > cutoff in the same read-only snapshot.

Both reports include confusion counts, precision, recall, false-positive rate,
alert rate, peak alerts per observed step and the number of steps exceeding the
prespecified capacity. Undefined rates remain null. Capacity feasibility during
selection is not a guarantee: later workload or behavior may breach it.

## Source and protocol controls

The workflow requires a static non-WAL SQLite source. It checks path, byte size
and nanosecond modification time before/after each stage and between stages.
This is a change detector, not a cryptographic source-content fingerprint or an
authenticity check. The protocol SHA-256 detects accidental JSON changes; it is
not a signature and can be recomputed by someone editing the file.

The source is opened read-only, reports are created exclusively, and the protocol
and result files are not a multi-user experiment registry. There is no query
timeout, retry, continuous monitoring, or hard cap on production alert execution.

## Tests and interpretation

Fourteen new test methods bring the full suite to 97 tests. They check complete
time-step grouping, manually computed period counts, capacity selection,
deterministic tie-breaking, future-label independence, no feasible choice,
undefined recall, invalid records, missing/changed/WAL sources, protocol changes,
read-only behavior, separate CLI stages, and output preservation.

One controlled test deliberately meets capacity in the selection period but
exceeds it later. It verifies that this limitation is reported rather than hidden.
These tests validate the software protocol, not real-world fraud detection.

After inspecting a holdout, changing the grid, cutoff or policy and repeatedly
checking that same holdout makes it part of development. It is no longer an
untouched final test. Record the protocol before evaluation and reserve a fresh
test period for subsequent research claims. Synthetic labels, the TRANSFER-only
rule, and the absence of a production cost model further limit generalization.
