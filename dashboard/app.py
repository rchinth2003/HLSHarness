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


def _resolve_db_path() -> Path | None:
    """Return the RunStore db path: second CLI arg, or default if it exists."""
    args = sys.argv[1:]
    if len(args) >= 2:
        return Path(args[1])
    default = Path(".hls_runs.db")
    return default if default.exists() else None


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


def _render_run_history(agent: str, db_path: Path) -> None:
    """Render run history table and baseline-promotion UI."""
    import pandas as pd

    from hlsharness.run_store import RunStore

    st.divider()
    st.subheader("Run History")

    store = RunStore(db_path=db_path)
    records = store.history(agent, limit=50)

    if not records:
        st.info("No run history found. Run `hls-eval` to populate the history.")
        return

    # Collect category names in first-seen order (stable columns)
    seen_cats: set[str] = set()
    all_cats: list[str] = []
    for r in records:
        for c in r.categories:
            if c.category not in seen_cats:
                seen_cats.add(c.category)
                all_cats.append(c.category)

    rows = []
    for r in records:
        cat_map = {c.category: c for c in r.categories}
        row: dict[str, object] = {
            "ID": r.id,
            "Version": r.version or "—",
            "SHA": r.git_sha[:7] if r.git_sha else "—",
            "Date": r.run_at[:19].replace("T", " "),
            "Pass": "✓" if r.passed else "✗",
            "Baseline": "★" if r.is_baseline else "",
        }
        for cat in all_cats:
            cs = cat_map.get(cat)
            if cs:
                marker = "✓ " if cs.met_threshold else "✗ "
                row[cat.capitalize()] = marker + _pct(cs.pass_rate)
            else:
                row[cat.capitalize()] = "—"
        rows.append(row)

    df = pd.DataFrame(rows)
    cat_cols = [cat.capitalize() for cat in all_cats]

    def _color_pass(val: str) -> str:
        if val == "✓":
            return f"color: {_PASS_COLOR}; font-weight: bold"
        if val == "✗":
            return f"color: {_FAIL_COLOR}; font-weight: bold"
        return ""

    def _color_baseline(val: str) -> str:
        return "color: #f59e0b; font-weight: bold" if val == "★" else ""

    def _color_cat(val: object) -> str:
        if isinstance(val, str) and val.startswith("✗"):
            return f"color: {_FAIL_COLOR}"
        if isinstance(val, str) and val.startswith("✓"):
            return f"color: {_PASS_COLOR}"
        return ""

    styled = df.style.map(_color_pass, subset=["Pass"]).map(_color_baseline, subset=["Baseline"])
    if cat_cols:
        styled = styled.map(_color_cat, subset=cat_cols)

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Baseline promotion
    passing_records = [r for r in records if r.passed]
    if passing_records:
        st.markdown("**Promote a run to baseline**")
        options = {
            r.id: f"#{r.id}  {r.run_at[:19].replace('T', ' ')}  v{r.version or '—'}"
            for r in passing_records
        }
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            selected_id: int = st.selectbox(
                "run",
                options=list(options.keys()),
                format_func=lambda x: options[x],
                key="baseline_promote_select",
                label_visibility="collapsed",
            )
        with col_btn:
            if st.button("⭐ Set as Baseline", key="baseline_promote_btn"):
                store.promote_baseline(selected_id)
                st.success(f"Run #{selected_id} set as baseline.")
                st.rerun()
    else:
        st.caption("No passing runs available to promote.")


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

    db_path = _resolve_db_path()
    if db_path is not None:
        _render_run_history(results.agent, db_path)


main()
