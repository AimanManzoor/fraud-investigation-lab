# Fraud Investigation Lab

An ongoing portfolio project for exploring suspicious transactions,
evaluating fraud-alert methods, and supporting evidence-based human review.

Built toward an interactive Streamlit application using Python and SQLite.

## Current status

- PaySim CSV downloaded locally.
- Dataset header checked: all 11 expected columns are present.
- SQLite ingestion, cleaning, detection, evaluation, and the app are planned.
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
- [ ] Reproducible SQLite ingestion
- [ ] SQL data-quality report and documented cleaning
- [ ] Baseline alert rules
- [ ] ML baseline and chronological evaluation
- [ ] Interactive Streamlit app
- [ ] Automated regression tests
- [ ] Hosted demo and final evaluation report

## Learning goals

SQL data engineering, data-quality validation, imbalanced classification,
human review workflows, interactive analytics, and reproducible evaluation.
