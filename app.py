"""Local transaction exploration; no prediction or review writes."""
import sqlite3
from pathlib import Path

import streamlit as st

from src.explorer import TYPES, explore
from src.demo import NOTICE, explore_demo

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

        submitted = st.form_submit_button("Apply filters")

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
