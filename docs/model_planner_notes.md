# Study notes: an AI planner inside a controlled harness

## What this milestone adds

An optional Anthropic Messages API client proposes a small JSON plan. The
existing Python harness decides whether that plan is permitted and whether its
returned evidence meets the implemented checks. The default investigation CLI
remains deterministic. Streamlit does not automatically make model calls.

Status: implementation and offline tests completed. No live provider request or
LLM task-performance benchmark has been run for this milestone. API availability
and the model ID must be checked using your own Anthropic account.

## Understand the three roles

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

## Boundaries to remember

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

Expected suite size: 65 tests. Eight added tests use simulated provider responses.
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

## Add your creativity deliberately

Use docs/my_investigation_design.md to propose one small investigation feature.
An example is a human-review note for a TRANSFER above a threshold you define.
The note must describe an observable condition, not declare fraud.

Before coding it:
1. Define the user, decision, units, time scope and exact rule.
2. Write a positive example, a negative example and a boundary example.
3. Specify whether the existing tool returns enough evidence. A full-account
   total needs an aggregate query, not a sum of the displayed rows.
4. Separate your business rule from the model prompt and harness permissions.
5. Implement one feature and run the existing tests plus independent new checks.

For a later experiment, keep the model and reference tasks fixed. Compare an
unconstrained proposal baseline with the harnessed version in isolated test
environments. Measure valid task completion, rejected unsafe plans, incorrect
acceptances, unnecessary rejections, query count, elapsed time and provider usage.
Use held-out questions and repeated runs. Do not let the model edit the checks
or reference answers, and report both gains and costs.

## Self-explanation prompts

- Where does a proposed action become an authorized action?
- Why is JSON parsing different from executing model-written code?
- How would an account-ID mismatch be detected?
- Why are planner_error and tool_error different?
- What can still be wrong after every current check passes?
- Why is a receipt evidence of execution, not evidence of fraud?

## References

- https://platform.claude.com/docs/en/api/messages/create
- https://platform.claude.com/docs/en/api/versioning
- https://github.com/walkinglabs/learn-harness-engineering
