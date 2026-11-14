# Fraud Investigation Lab

An ongoing portfolio project for exploring suspicious transactions,
evaluating fraud-alert methods, and supporting evidence-based human review.

Built toward an interactive Streamlit application using Python and SQLite.

## Current status

- PaySim CSV downloaded locally.
- Dataset header checked: all 11 expected columns are present.
- SQLite ingestion and an initial SQL data-quality report are implemented.
- Forty-two regression tests cover data processing, explorer queries, demo export, and Streamlit interactions on controlled fixtures.
- Full-dataset numeric audit completed: 6,362,620 records and zero invalid cells under the implemented rules.
- Typed transaction data is implemented with exact amount conversion at scale 100.
- A read-only Streamlit explorer is implemented and tested on controlled fixtures. Full-dataset UI verification is pending.
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
Dataset attribution and applicable usage terms will be documented.

## Planned workflow

1. Load the original CSV into a raw SQLite table.
2. Audit missing values, types, invalid values, and duplicate candidates.
3. Create documented clean tables or views without silently deleting records.
4. Build transparent alert rules and compare a simple ML baseline.
5. Evaluate using chronological training, validation, and test periods.
6. Build and deploy an interactive Streamlit investigation app.

## Planned app features

- Transaction filters for amount, type, time step, and risk score.
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
- [ ] SQL data-quality report and documented cleaning
- [ ] Baseline alert rules
- [ ] ML baseline and chronological evaluation
- [x] Local read-only Streamlit explorer tested on controlled fixtures
- [ ] Full-dataset UI acceptance check
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
The app uses the existing typed database; no rebuild is required.

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
