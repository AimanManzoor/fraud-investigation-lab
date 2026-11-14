# Curated PaySim demo data

Source: Synthetic Financial Datasets For Fraud Detection, by Edgar A.
Lopez-Rojas, published on Kaggle:
https://www.kaggle.com/datasets/ealaxi/paysim1

The adapted demo dataset is distributed under CC BY-SA 4.0:
https://creativecommons.org/licenses/by-sa/4.0/

Reference: E. A. Lopez-Rojas, A. Elmir, and S. Axelsson.
PaySim: A financial mobile money simulator for fraud detection.
European Modeling and Simulation Symposium, 2016.

Changes: selected a subset of transactions, retained eight typed fields,
renamed source columns, and represented amounts as scale-100 integers.
The source CSV fingerprint is retained in transactions.json.

Selection: up to 500 earliest records per transaction type, plus up to
100 fraud-labeled and 100 legacy-flagged records. Each record ID appears
once in the exported sample. Distinct records with identical attributes
are preserved.

This is a curated demonstration sample, not a representative sample.
Do not use its label proportions to estimate population fraud prevalence
or evaluate a fraud model. The complete local dataset remains separate.

This notice applies to the adapted demo data.
