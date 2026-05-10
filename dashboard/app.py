"""HLS Harness — Streamlit dashboard.

Launch via the harness CLI::

    python harness.py run --agent scheduling-v1 --serve

Or directly::

    streamlit run dashboard/app.py -- results.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from dashboard.loader import DashCaseSummary, DashResults, load_results

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HLS Agent Eval",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CATEGORY_ICONS: dict[str, str] = {
    "functional": "⚙️",
    "safety": "🛡️",
    "privacy": "🔒",
    "equity": "⚖️",
    "operational": "📊",
}

_PASS_COLOR = "#00b386"
_FAIL_COLOR = "#e05c5c"


# ── helpers ───────────────────────────────────────────────────────────────────


def _resolve_results_path() -> Path:
    """Return the results.json path from CLI args or default."""
    args = sys.argv[1:]
    if args:
        return Path(args[0])
    return Path("results.json")


def _badge(passed: bool) -> str:
    color = _PASS_COLOR if passed else _FAIL_COLOR
    label = "PASS" if passed else "FAIL"
    return f'<span style="color:{color};font-weight:bold">{label}</span>'


def _pct(value: float) -> str:
    return f"{value:.0%}"


# ── main ─────────────────────────────────────────────────────────────────────


def _render_header(results: DashResults) -> None:
    overall_color = _PASS_COLOR if results.passed else _FAIL_COLOR
    overall_label = "✓ PASSED" if results.passed else "✗ FAILED"

    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.title("HLS Agent Evaluation Dashboard")
        st.caption(f"**Agent:** {results.agent}  |  **Run:** {results.run_at}")
    with col_status:
        st.markdown(
            f"""
            <div style="
                background:{overall_color}22;
                border:2px solid {overall_color};
                border-radius:8px;
                padding:16px;
                text-align:center;
                font-size:1.4rem;
                font-weight:bold;
                color:{overall_color};
                margin-top:12px;
            ">{overall_label}</div>
            """,
            unsafe_allow_html=True,
        )


def _render_kpis(results: DashResults) -> None:
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases", results.total_cases)
    c2.metric(
        "Cases Passed",
        f"{results.total_passed} / {results.total_cases}",
        f"{results.overall_pass_rate:.0%}",
    )
    c3.metric("Avg Latency", f"{results.avg_latency_ms:.0f} ms")
    c4.metric("Total Tokens", f"{results.total_tokens:,}")
    st.divider()


def _render_category_scorecards(results: DashResults) -> None:
    st.subheader("Category Gates")
    cols = st.columns(len(results.categories) or 1)
    for col, cat in zip(cols, results.categories, strict=False):
        icon = _CATEGORY_ICONS.get(cat.category, "📋")
        color = _PASS_COLOR if cat.met_threshold else _FAIL_COLOR
        with col:
            st.markdown(
                f"""
                <div style="
                    border:2px solid {color};
                    border-radius:10px;
                    padding:16px 12px;
                    text-align:center;
                ">
                    <div style="font-size:1.8rem">{icon}</div>
                    <div style="font-weight:bold;font-size:1rem;margin:4px 0">
                        {cat.category.capitalize()}
                    </div>
                    <div style="font-size:1.6rem;font-weight:bold;color:{color}">
                        {_pct(cat.pass_rate)}
                    </div>
                    <div style="font-size:0.8rem;color:#888">
                        threshold {_pct(cat.threshold)}
                    </div>
                    <div style="font-size:0.75rem;margin-top:4px">
                        {cat.passed_count}/{cat.total} passed
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_cases_table(cases: list[DashCaseSummary]) -> None:
    import pandas as pd

    rows = [
        {
            "ID": c.case_id,
            "Category": c.category,
            "Score": round(c.score, 3),
            "Pass": "✓" if c.passed else "✗",
            "Latency (ms)": round(c.latency_ms),
            "Tokens": c.total_tokens,
            "Input": c.input_summary[:80] + ("…" if len(c.input_summary) > 80 else ""),
        }
        for c in cases
    ]
    df = pd.DataFrame(rows)

    def _color_pass(val: str) -> str:
        if val == "✓":
            return f"color: {_PASS_COLOR}; font-weight: bold"
        return f"color: {_FAIL_COLOR}; font-weight: bold"

    st.dataframe(
        df.style.map(_color_pass, subset=["Pass"]),
        use_container_width=True,
        hide_index=True,
    )


def _render_category_detail(results: DashResults) -> None:
    st.subheader("Category Detail")
    tabs = st.tabs(
        [
            f"{_CATEGORY_ICONS.get(cat.category, '📋')} {cat.category.capitalize()}"
            for cat in results.categories
        ]
    )
    for tab, cat in zip(tabs, results.categories, strict=False):
        with tab:
            cases = results.cases_for_category(cat.category)
            _render_cases_table(cases)

            with st.expander("Case transcripts"):
                for case in cases:
                    status = "✓" if case.passed else "✗"
                    color = _PASS_COLOR if case.passed else _FAIL_COLOR
                    st.markdown(
                        f"**{status} {case.case_id}** — score `{case.score:.3f}` "
                        f"| {case.latency_ms:.0f} ms | {case.total_tokens} tokens",
                        unsafe_allow_html=False,
                    )
                    st.markdown(f"*{case.input_summary}*")
                    st.markdown(
                        f'<span style="color:{color}">**Rationale:** {case.rationale}</span>',
                        unsafe_allow_html=True,
                    )
                    if case.trajectory:
                        with st.expander(f"Tool trajectory ({len(case.trajectory)} calls)"):
                            import json

                            st.code(json.dumps(case.trajectory, indent=2), language="json")
                    if case.metadata:
                        cols = st.columns(len(case.metadata))
                        for col, (k, v) in zip(cols, case.metadata.items(), strict=False):
                            col.metric(k, str(v))
                    st.divider()


def _render_sidebar(results: DashResults) -> None:
    with st.sidebar:
        st.header("HLS Harness")
        st.markdown(f"**Agent:** `{results.agent}`")
        st.markdown(f"**Run:** {results.run_at[:19].replace('T', ' ')}")
        st.divider()
        st.markdown("**Category gates**")
        for cat in results.categories:
            icon = "✅" if cat.met_threshold else "❌"
            st.markdown(
                f"{icon} **{cat.category}** — {_pct(cat.pass_rate)} / {_pct(cat.threshold)}"
            )
        st.divider()
        st.caption("HLS Agent Evaluation Harness · Slice 3")


def main() -> None:
    results_path = _resolve_results_path()

    if not results_path.exists():
        st.error(
            f"Results file not found: `{results_path}`\n\n"
            "Run the harness first:\n```\npython harness.py run --agent scheduling-v1\n```"
        )
        st.stop()

    try:
        results = load_results(results_path)
    except (ValueError, KeyError) as exc:
        st.error(f"Could not parse results file: {exc}")
        st.stop()

    _render_sidebar(results)
    _render_header(results)
    _render_kpis(results)
    _render_category_scorecards(results)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_category_detail(results)


main()
