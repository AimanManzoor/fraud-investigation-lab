# Fraud Investigation Lab

An ongoing portfolio project for exploring suspicious transactions,
evaluating fraud-alert methods, and supporting evidence-based human review.

Interactive transaction exploration using Streamlit, Python, and SQLite.


## Try the interactive demo

The repository includes a small demo dataset. You do **not** need the full
PaySim CSV, a local database, API keys, or an LLM account to try it.

### Run locally (macOS or Linux)

Use Python 3.12, the version used for validation. In Terminal:

```bash
git clone https://github.com/AimanManzoor/fraud-investigation-lab.git
cd fraud-investigation-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv`.
Then run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and
`.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1`.

Open the local URL printed in Terminal, usually http://127.0.0.1:8501.
Keep Terminal running while using the app; press **Control+C** to stop it.
This local address works on your computer. Other visitors must run their own
copy or use a separately deployed hosted demo.

### What to do in the app

1. Choose **Demo sample** under **Data source**.
2. Click **Apply filters** to load results.
3. Filter transaction type, simulation time step, amount, dataset fraud label,
   or legacy rule flag, then click **Apply filters** again.
4. Select a displayed **Record ID** beneath the table to inspect its details.

The included sample has **2,579 transactions**, **116 dataset fraud labels**,
and **16 legacy flags**. These default totals apply to the included snapshot.
It deliberately includes additional fraud and flagged examples. It is
**not representative of the full dataset**; its label proportions must not
be used to estimate population fraud rates or model performance.

Metrics and the chart cover all matching records in the **selected source**.
The table displays only the first 200 matches in record-ID order.
Amounts use dataset units with exact scale-100 storage, without assuming a
currency. Steps are simulation hours, not calendar dates.

With no full local database, the app defaults to Demo sample. If an existing
`data/fraud_typed.db` is present, it defaults to Full local database; select
Demo sample explicitly to try the shareable version. Switching sources clears
previous results. Full-data preparation is documented below.

### Run the tests

After installing dependencies and activating the environment:

```bash
python -m unittest discover -s tests -t . -v
```

The suite has 42 tests, using controlled temporary databases. An additional
Streamlit AppTest check of the committed demo snapshot successfully displayed
2,579 / 116 / 16 with no full local database.

### Troubleshooting

- **Demo sample missing:** confirm `demo/transactions.json` is present and
  that you cloned the complete repository.
- **Typed database missing:** choose Demo sample, or prepare the full local
  typed database using the ingestion and typed-layer instructions below.
- **Filters appear unchanged:** click Apply filters; results reflect the last
  submitted filter values.
- **Amount precision error:** enter an amount exactly representable at scale
  100, such as `12.34`. Values such as `0.001` are rejected without rounding.
- **No matching transactions:** broaden the filters. Demo results reflect
  the curated sample, not all 6.36 million source records.

## Current status

- PaySim CSV downloaded locally.
- Dataset header checked: all 11 expected columns are present.
- SQLite ingestion and an initial SQL data-quality report are implemented.
- Forty-two regression tests cover data processing, explorer queries, demo export, and Streamlit interactions on controlled fixtures.
- Full-dataset numeric audit completed: 6,362,620 records and zero invalid cells under the implemented rules.
- Typed transaction data is implemented with exact amount conversion at scale 100.
- The read-only Streamlit explorer supports the full local database and a committed demo sample.
- The committed demo snapshot runs without the full database. The full-data aggregate check was observed locally; further full-data UI verification and benchmarking remain pending.
- Duplicate assessment, balance-field precision, detection, analyst review, and deployment remain pending.
- No predictive performance results have been established yet.

## Problem

Fraud alerts need more than a prediction. Reviewers need relevant transaction
evidence, clear alert reasons, and a way to record their decisions.

This project will connect data-quality checks, SQL analysis, fraud scoring,
and an interactive investigation interface.

## Dataset

Source: [PaySim on Kaggle](https://www.kaggle.com/datasets/ealaxi/paysim1).

PaySim contains synthetic mobile-money transactions and simulated fraud labels.
It does not represent validated production fraud-detection performance.

The original CSV remains unchanged in data/raw/ and is excluded from Git.
Sample attribution, adaptation details, and the data-license link are documented in [demo/README.md](demo/README.md).

## Planned workflow

1. Load the original CSV into a raw SQLite table.
2. Audit missing values, types, invalid values, and duplicate candidates.
3. Create documented clean tables or views without silently deleting records.
4. Build transparent alert rules and compare a simple ML baseline.
5. Evaluate using chronological training, validation, and test periods.
6. Build and deploy an interactive Streamlit investigation app.

## App scope and planned extensions

- Implemented: filters for amount, type, simulation step, dataset fraud label, and legacy flag.
- Planned: risk-score filtering once a detector is implemented and evaluated.
- Charts showing transaction volumes and alert patterns.
- Transaction details and available earlier account activity.
- Explanations of the rules that triggered an alert.
- A review queue with analyst notes and dispositions.
- Evaluation results showing precision, recall, and alert volume.

Analyst decisions will be stored separately from the original dataset labels.
A suspicious transaction is an alert, not proof of fraud.

## Evaluation principles

- Keep fraud labels out of prediction inputs.
- Use only information available at the defined decision time.
- Audit balance-related fields for outcome artifacts before considering them.
- Calculate historical features from earlier time steps.
- Keep transactions from the same time step in the same temporal split.
- Fit preprocessing on training data and choose thresholds on validation data.
- Report held-out results and class imbalance rather than accuracy alone.

## Potential REA extension

Explore using REA to inspect supported application behavior, network requests,
and SQLite structure. REA integration is optional and not implemented yet.

## Roadmap

- [x] Download dataset and verify expected columns
- [x] Reproducible SQLite ingestion
- [x] Initial SQL quality report and full numeric audit
- [x] Exact amount conversion and reconciled typed transaction layer
- [ ] Duplicate assessment and balance-field audit
- [ ] Baseline alert rules
- [ ] ML baseline and chronological evaluation
- [x] Local read-only Streamlit explorer tested on controlled fixtures
- [x] Committed demo sample and source switching
- [x] Demo verified without the full local database
- [ ] Further full-dataset UI acceptance checks and benchmarking
- [ ] Scoring and analyst review features
- [x] Automated ingestion regression tests
- [ ] Hosted demo and final evaluation report

## Learning goals

SQL data engineering, data-quality validation, imbalanced classification,
human review workflows, interactive analytics, and reproducible evaluation.

## Run ingestion and tests

- Import once: `python3 src/ingest.py`
- Test: `python3 -m unittest discover -s tests -t . -p 'test_ingest.py' -v`
- Raw values are preserved; existing databases are not overwritten.
- Initial checks cover record counts, blanks, labels, and transaction types.
- Exact amount conversion and the typed layer are implemented. Duplicate assessment and balance-field precision remain pending.
- Local data, databases, and generated reports are excluded from Git.

## Numeric validation helper

`src/validation.py` classifies numeric text without changing raw values.
It checks missing values, numeric format, finiteness, negative values,
positive integer steps, and supported numeric ranges.

The helper has been tested on controlled examples and applied to the full
dataset. A separate typed layer is implemented; further cleaning and duplicate assessment remain pending.

Run all tests: `python3 -m unittest discover -s tests -t . -v`

## Full-dataset numeric audit

- Run: `python3 -m src.audit_numeric`
- Checks step, amount, and four balance columns using a read-only connection.
- Observed result: 6,362,620 records; zero invalid cells under the current rules.
- Generated report: `reports/generated/numeric_report.json` (not committed).
- Passing these rules does not establish overall data quality or model readiness.

## Typed transaction layer

- Builder: `src/build_typed.py`
- Exact amount conversion: `src/money.py`
- Build command: `python3 -m src.build_typed`
- Observed source and output counts: 6,362,620 records each.
- Amounts are stored as integer units at scale 100; unsupported precision is rejected.
- Original record IDs and duplicate candidates are preserved.
- Raw data remains unchanged; balances remain in the raw database.
- Query indexes cover time step and transaction type.
- Existing output databases are not overwritten.
- Fraud labels and legacy flags support evaluation, not prediction inputs.
- Local databases and generated reports are excluded from Git.


## Local transaction explorer

A local exploration prototype over `data/fraud_typed.db`.

Implemented:
- Filters for transaction type, inclusive time-step range, exact amount
  range, dataset fraud label, and legacy rule flag.
- Read-only parameterized SQLite queries.
- Metrics and a transaction-type chart covering ALL matching records.
- A table limited to the first 200 matches in record-ID order.
- Detail inspection for displayed transactions.
- Exact amount display using integer arithmetic.
- Invalid-input and missing-database messages.

Run from the repository root:

1. Create an environment: `python3 -m venv .venv`
2. Install dependencies: `.venv/bin/python -m pip install -r requirements.txt`
3. Run tests: `.venv/bin/python -m unittest discover -s tests -t . -v`
4. Launch: `.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1`

Open the local URL printed by Streamlit. Press Control+C to stop the server.
Full local database mode uses the existing typed database; no rebuild is required.
Demo sample mode works without that database.

Click Apply filters to submit changes. Amounts use dataset units, without
assuming a currency. Time steps are simulation hours, not calendar dates.

Validation:
- 25 existing ingestion, validation, audit, money, and typed-layer tests.
- Eight explorer-query tests and three Streamlit interaction tests.
- Tests use controlled temporary databases.
- Full-dataset UI verification and performance benchmarking remain pending.
- Aggregate counts scan matching records; bounded display does not guarantee
  fast queries over the full dataset.

This prototype does not predict fraud, calculate risk scores, store analyst
decisions, or implement an autonomous agent. Dataset fraud labels are
simulated outcomes; the legacy rule flag is a separate historical field.
Raw data and local databases remain excluded from Git.


## Shareable demo mode

The app offers Demo sample and Full local database sources.
On a fresh machine without the full database, it defaults to Demo sample.

- Demo input: `demo/transactions.json`, a curated PaySim subset.
- Export once locally: `.venv/bin/python -m src.demo`
- Existing sample files are not overwritten.
- Up to 500 earliest records per type, plus up to 100 fraud-labeled
  and 100 legacy-flagged cases, with unique record IDs.
- The sample is not representative. Its fraud rate is not a population estimate.
- Original record IDs and exact scale-100 amounts are preserved.
- Full local databases remain excluded from Git.
- Demo queries build a small temporary SQLite database and reuse the
  same read-only explorer query layer.
- Changing sources clears previous results.
- Sample attribution and data-license details appear in demo/README.md.

The six new tests cover reproducibility, source preservation, querying
without the full database, overwrite protection, missing inputs, invalid
sample values, and source switching in the UI.

Observed full-data aggregate check: 6,362,620 transactions,
8,213 dataset fraud labels, and 16 legacy flags.
This check does not establish model performance.

Hosting status: deployment and live-URL verification are pending.
For Streamlit Community Cloud, select this repository, branch main,
and entrypoint app.py. A hosted demo does not require the full local
database because the curated JSON sample is included in the repository.

## Deploy a shareable Streamlit app

**Status: deployment and a verified live URL are still pending.** The code and
demo data are available on GitHub; pushing code does not deploy the app.

1. Sign in at https://share.streamlit.io/ and connect the GitHub account that
   has access to the repository.
2. Choose **Create app**, then the option to deploy an existing GitHub app.
3. Enter these values in the deployment form:

   | Field | Value |
   |---|---|
   | Repository | `AimanManzoor/fraud-investigation-lab` |
   | Branch | `main` |
   | Main file path | `app.py` |
   | Python version (Advanced settings) | `3.12` |

4. Deploy. Dependencies are declared in `requirements.txt`. No API keys or
   application secrets are needed for this explorer.
5. Open the assigned app URL, choose **Demo sample**, and click **Apply filters**.
   With default filters, verify the 2,579 / 116 / 16 snapshot totals.
6. Verify type and amount filters, record details, empty results, and the
   precision-error message. Check that clearing/changing filters behaves as expected.
7. Once the hosted app has been checked, add its actual URL to this README and
   the repository **About → Website** field. Share that URL with visitors.

The committed `demo/transactions.json` makes demo mode self-contained.
The full local SQLite databases are excluded from Git and are not available
to the deployed app. Selecting Full local database on the host will report
a missing database unless one is supplied separately.

The demo is a read-only exploration prototype. It provides no fraud predictions,
production performance claims, or analyst decision storage.

Deployment reference:
[Streamlit Community Cloud documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
