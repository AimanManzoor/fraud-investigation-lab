"""Local transaction exploration; no prediction or review writes."""
import sqlite3
import json
from pathlib import Path

import streamlit as st

from src.explorer import TYPES, explore
from src.demo import NOTICE, explore_demo
from src.alert_evaluation import evaluate_source

DEFAULT_DATABASE = Path(__file__).resolve().parent / "data/fraud_typed.db"


def main(database=None):
    st.set_page_config(page_title="Fraud Investigation Lab", layout="wide")
    st.title("Fraud Investigation Lab")
    st.caption("Transaction explorer · synthetic PaySim data")

    query = explore
    if database is None:
        mode = st.radio(
            "Data source",
            ("Demo sample", "Full local database"),
            index=1 if DEFAULT_DATABASE.is_file() else 0,
        )
        if mode == "Demo sample":
            database = DEFAULT_DATABASE.parents[1] / "demo/transactions.json"
            query = explore_demo
            st.warning(NOTICE)
        else:
            database = DEFAULT_DATABASE
            st.caption("Full local database selected; the demo sample is not used.")

    database = Path(database)
    source_key = (
        str(database.resolve()),
        database.stat().st_mtime_ns if database.is_file() else None,
    )
    if st.session_state.get("explorer_source") != source_key:
        st.session_state.pop("explorer_result", None)
        st.session_state.pop("legacy_evaluation", None)
        st.session_state["explorer_source"] = source_key


    st.info(
        "Dataset fraud labels and legacy rule flags are separate historical fields. "
        "This prototype does not predict fraud or calculate a risk score."
    )
    st.caption(
        "Amounts use dataset units, with exact scale-100 storage. "
        "Time steps are simulation hours, not calendar dates."
    )

    with st.form("filters"):
        left, right = st.columns(2)

        with left:
            kind = st.selectbox("Transaction type", ("All",) + TYPES)
            step_min = st.number_input(
                "Minimum time step", min_value=1, value=1, step=1
            )
            maximum_step = st.text_input("Maximum time step (optional)")
            minimum_amount = st.text_input("Minimum amount", value="0")

        with right:
            maximum_amount = st.text_input("Maximum amount (optional)")
            fraud = st.selectbox("Dataset fraud label", ("All", "0", "1"))
            legacy = st.selectbox("Legacy rule flag", ("All", "0", "1"))
            account_id = st.text_input(
                "Account ID (optional)", max_chars=128,
                help="Exact, case-sensitive ID; matches sender or recipient.",
            )

        submitted = st.form_submit_button("Apply filters")

    with st.expander("Evaluate the recorded legacy alert flag", expanded=False):
        st.caption('Compare legacy_flag with the synthetic is_fraud label across the ENTIRE selected source. Transaction filters, account search, and the 200-row display limit do not apply.')
        st.caption('This measures an existing recorded flag; it does not train a model, produce new alerts, or establish causation.')
        if st.button('Evaluate selected source', key='evaluate_legacy'):
            st.session_state.pop('legacy_evaluation', None)
            try:
                st.session_state['legacy_evaluation'] = evaluate_source(
                    database, source_kind='demo' if query is explore_demo else 'full')
            except (ValueError, FileNotFoundError, sqlite3.Error):
                st.error('Evaluation unavailable. Check the selected source and its binary label/flag fields.')
        evaluation = st.session_state.get('legacy_evaluation')
        if evaluation is not None:
            st.warning(evaluation['notice'])
            st.caption(f"Evaluated {evaluation['total_records']:,} records from {evaluation['source_kind']} source. Undefined rates display N/A; JSON uses null.")
            columns = st.columns(4)
            for column, (name, value) in zip(columns, evaluation['metrics'].items()):
                column.metric(name.replace('_', ' ').title(), 'N/A' if value is None else f'{value:.2%}')
            st.dataframe([
                {'Dataset label': 'Fraud = 1', 'Flag = 1 (alert)': evaluation['confusion_counts']['true_positives'],
                 'Flag = 0 (no alert)': evaluation['confusion_counts']['false_negatives']},
                {'Dataset label': 'Fraud = 0', 'Flag = 1 (alert)': evaluation['confusion_counts']['false_positives'],
                 'Flag = 0 (no alert)': evaluation['confusion_counts']['true_negatives']},
            ], hide_index=True)
            st.download_button('Download legacy-flag evaluation', json.dumps(evaluation, indent=2),
                               file_name=f"legacy_evaluation_{evaluation['source_kind']}.json", mime='application/json')

    if submitted:
        try:
            with st.spinner("Querying the local database..."):
                result = query(
                    database,
                    kind=None if kind == "All" else kind,
                    step_min=step_min,
                    step_max=(
                        int(maximum_step.strip())
                        if maximum_step.strip() else None
                    ),
                    amount_min=minimum_amount.strip(),
                    amount_max=maximum_amount.strip() or None,
                    fraud=None if fraud == "All" else int(fraud),
                    legacy=None if legacy == "All" else int(legacy),
                    account_id=account_id.strip() or None,
                )
            st.session_state["explorer_result"] = result

        except (ValueError, FileNotFoundError) as error:
            st.session_state.pop("explorer_result", None)
            st.error(str(error))

        except sqlite3.Error:
            st.session_state.pop("explorer_result", None)
            st.error(
                "Cannot query the typed database. "
                "Check that its build completed successfully."
            )

    result = st.session_state.get("explorer_result")

    if result is None:
        st.write("Choose filters and click Apply filters to load transactions.")
        return

    st.caption(
        "Results reflect the last submitted filters. "
        "Click Apply filters after edits."
    )

    a, b, c = st.columns(3)
    a.metric("Matching transactions", f"{result['total']:,}")
    b.metric("Dataset fraud labels = 1", f"{result['fraud_labels']:,}")
    c.metric("Legacy flags = 1", f"{result['legacy_flags']:,}")

    if not result["rows"]:
        st.warning("No matching transactions. Try broader filters.")
        return

    st.subheader("Transaction counts by type")
    st.bar_chart(result["groups"], x="transaction_type", y="records")

    st.caption(
        "Totals and chart cover ALL matches. The table shows only the first "
        "200 matching records in record-ID order; it is not a random sample."
    )
    st.dataframe(result["rows"], hide_index=True)

    st.subheader("Inspect a displayed transaction")
    by_id = {row["record_id"]: row for row in result["rows"]}
    selected = st.selectbox("Record ID", list(by_id))
    st.json(by_id[selected])


if __name__ == "__main__":
    main()
