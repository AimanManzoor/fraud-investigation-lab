# Investigation harness: first milestone

The harness validates a proposed plan, executes one bounded read-only account
search, checks returned evidence, and saves a final receipt.

The original CLI does not call a model. It creates a deterministic plan unless the
caller supplies --plan-json. This is the control layer for a future agent.

Allowed plan:

    {"tool":"search_account","account_id":"C1231006815","limit":20}

The account must match the user request exactly. No additional plan fields
are accepted. Limit must be an integer from 1 to 50. The caller selects the
source; a plan cannot select arbitrary source paths or execute SQL.

Run:

    python -m src.investigation_harness --account-id C1231006815 --source demo

For the full local database, use --source full.

Statuses:
- completed
- no_matches
- rejected
- tool_error
- verification_failed

Completed means the scope and count-consistency checks passed. It does not
mean an account is fraudulent or safe. Human review is always required.
Checks do not independently recompute full-dataset totals or authenticate
every underlying record.

Each run allows one tool-call attempt without retries. The row and call
limits do not enforce a query timeout or wall-clock execution limit.

Evidence includes record references and transaction fields. Dataset fraud
labels and legacy flags are excluded. Demo history is explicitly partial.

Receipts are saved under reports/generated/harness_runs/, excluded from Git.
These are final receipts, not crash-recovery or session-resume checkpoints.

Nine additional tests bring the suite to 57. They cover plan rejection,
account scope, tool limits, source failures, injected evidence errors,
label exclusion, source preservation, and saved receipts.

The original milestone left model integration as a follow-up. An optional
planner adapter is now implemented; live verification and comparisons remain pending.
The model must not modify the checks or their reference answers.
No LLM effectiveness improvement has been measured yet.

## Optional planner follow-up

The first-milestone CLI above remains deterministic. A separate opt-in provider
adapter is now implemented in src/model_planner.py. It uses the same harness and
adds planner_error when configuration, network, or response parsing fails.
See model_planner.md for setup and technical details. Live API verification
and measured model performance remain pending. Total suite: 65 offline tests.
