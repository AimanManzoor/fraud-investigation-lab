# Working in Fraud Investigation Lab

- Read README.md and docs/investigation_harness.md before changing the workflow.
- Keep original data and full databases local.
- Do not commit credentials, model artifacts, or generated receipts.
- Reuse src/explorer.py and src/demo.py for read-only source access.
- Enforce tool permissions, account scope, and budgets in Python.
- Keep fraud labels and legacy flags out of model-facing evidence.
- Never treat execution success or no matches as a fraud verdict.
- Keep one small feature per change and test changed behavior.
- Run: python -m unittest discover -s tests -t . -v
- Tests must use temporary fixtures and must not call AI providers.
- Update README with implemented behavior and remaining limitations.
- Passing tests does not establish predictive accuracy or production readiness.
