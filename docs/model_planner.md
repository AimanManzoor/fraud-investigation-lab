# Optional model planner

## What this milestone adds

An optional Anthropic Messages API client proposes a small JSON plan. The
existing Python harness decides whether that plan is permitted and whether its
returned evidence meets the implemented checks. The default investigation CLI
remains deterministic. Streamlit does not automatically make model calls.

Status: implementation and offline tests completed. No live provider request or
LLM task-performance benchmark has been run for this milestone. API availability
and the model ID must be checked using your own Anthropic account.

## Architecture

| Role | Responsibility | It cannot establish |
|---|---|---|
| Model planner | Translate the question into a proposed tool and arguments | Permission to execute, factual truth, or fraud |
| Harness | Check tool name, account scope, arguments, row limit and call budget | Whether every natural-language intention was understood |
| SQL tool | Retrieve matching records from the selected source | Whether an account is fraudulent or safe |

Example plan:

    {"tool":"search_account","account_id":"C1231006815","limit":10}

The model's text is parsed as data. It is never evaluated as Python, shell code,
or SQL. Code fences, duplicate JSON keys, truncated responses and oversized
responses are rejected. Valid JSON still has to pass the existing plan checks.

## Trace one request

1. The caller selects the account and demo/full source. The model cannot select
   a file path or another account.
2. Local checks validate input lengths, configuration and source-file existence.
3. One request sends the question, account ID, source kind and fixed instructions
   to Anthropic. Database rows and dataset labels are not supplied by the app.
4. The response must finish normally and contain a parseable JSON plan.
5. The harness permits only search_account, the requested account, and an integer
   row limit of 1-50. Extra arguments are rejected before the evidence query.
6. The existing read-only tool runs once. The harness checks account scope,
   displayed-row count, grouped counts, reference uniqueness and amount format.
7. A final receipt records the stages and outcomes. Human review stays required.

Existing investigation statuses still apply. A provider/configuration/response
failure adds planner_error, with zero evidence-tool calls. A bad but parseable
plan returns rejected. The error type is recorded without raw provider bodies.

## Limitations

- One planner request is separate from the one permitted evidence-tool attempt.
- max_tokens=256 is an output-token limit, not a fixed dollar budget.
- A 30-second socket timeout is not a total pipeline deadline.
- There are no automatic planner or evidence-tool retries. Failed requests may
  still incur provider usage charges.
- Matching source IDs and consistent counts do not prove factual truth.
- A valid plan can misunderstand the question. For example, a question requesting
  ten records could produce limit=20, which is allowed by the harness. Intent
  correctness needs separate reference cases and evaluation.
- Demo data is curated and partial. Full-source results can also display only
  a bounded subset. Do not describe displayed records as complete history.
- Dataset fraud labels and legacy flags are excluded from investigation evidence.
  The model proposes retrieval; it does not perform fraud detection.
- Raw questions, API keys and raw provider responses are not written into receipts.
  Receipts still contain synthetic account identifiers and evidence. They stay local.

## Run and inspect

Offline checks (no API key, network request, or charge):

    python -m unittest discover -s tests -t . -v

Current suite size: 83 tests. Eight added tests use simulated provider responses.
These test software behavior, not whether a live model chooses good plans.

The live CLI is optional. Choose a currently available model ID from your own
Anthropic account and replace MODEL_ID before running:

    python -m src.model_planner --live --model MODEL_ID --account-id C1231006815 --source demo --question "Show ten transactions involving this account"

The key is read from ANTHROPIC_API_KEY or requested using a hidden terminal prompt.
Never paste the key into chat, a command argument, a tracked file, or a screenshot.
ANTHROPIC_MODEL can supply the model ID instead of --model. No .env file is loaded
automatically by this adapter. No additional Python package is required.

Inspect planner.request_attempts, tool_calls, status, steps, partial_history,
human_review_required, and planner.usage in the receipt saved under
reports/generated/harness_runs/. Model ID, usage and request-attempt count are
recorded when available; this is not a complete provider billing report.

## References

- https://platform.claude.com/docs/en/api/messages/create
- https://platform.claude.com/docs/en/api/versioning
