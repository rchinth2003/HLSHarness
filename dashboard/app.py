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

from dashboard.loader import (
    DashCaseSummary,
    DashResults,
    DashSolutionResult,
    load_results,
    load_solution_results,
)

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


def _resolve_solution_path() -> Path | None:
    """Return the solution_results.json path: third CLI arg, or default if it exists."""
    args = sys.argv[1:]
    if len(args) >= 3:
        return Path(args[2])
    default = Path("solution_results.json")
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


def _render_delta_view(agent: str, db_path: Path) -> None:
    """Render side-by-side category delta table and case flip list for two runs."""
    import pandas as pd

    from hlsharness.run_store import RunStore

    st.divider()
    st.subheader("Delta View")

    store = RunStore(db_path=db_path)
    records = store.history(agent, limit=50)

    if len(records) < 2:
        st.info("Need at least 2 runs to compare.")
        return

    options = {
        r.id: f"#{r.id}  {r.run_at[:19].replace('T', ' ')}  v{r.version or '—'}  {'✓' if r.passed else '✗'}"
        for r in records
    }
    ids = list(options.keys())

    col_a, col_b = st.columns(2)
    with col_a:
        id_a: int = st.selectbox(
            "Run A",
            options=ids,
            format_func=lambda x: options[x],
            index=1,
            key="delta_run_a",
        )
    with col_b:
        id_b: int = st.selectbox(
            "Run B",
            options=ids,
            format_func=lambda x: options[x],
            index=0,
            key="delta_run_b",
        )

    if id_a == id_b:
        st.warning("Select two different runs to compare.")
        return

    rec_a = next(r for r in records if r.id == id_a)
    rec_b = next(r for r in records if r.id == id_b)

    cats_a = {c.category: c.pass_rate for c in rec_a.categories}
    cats_b = {c.category: c.pass_rate for c in rec_b.categories}
    all_cats = sorted(set(cats_a) | set(cats_b))

    rows = []
    for cat in all_cats:
        a = cats_a.get(cat)
        b = cats_b.get(cat)
        delta = (b - a) if (a is not None and b is not None) else None
        rows.append(
            {
                "Category": cat.capitalize(),
                "Run A": _pct(a) if a is not None else "—",
                "Run B": _pct(b) if b is not None else "—",
                "Delta (B−A)": f"{delta:+.0%}" if delta is not None else "—",
            }
        )

    def _color_delta(val: object) -> str:
        if not isinstance(val, str) or val == "—":
            return ""
        if val.startswith("+"):
            return f"color: {_PASS_COLOR}; font-weight: bold"
        if val.startswith("-"):
            return f"color: {_FAIL_COLOR}; font-weight: bold"
        return ""

    st.dataframe(
        pd.DataFrame(rows).style.map(_color_delta, subset=["Delta (B−A)"]),
        use_container_width=True,
        hide_index=True,
    )

    cases_a_raw = store.cases_for_run(id_a)
    cases_b_raw = store.cases_for_run(id_b)

    if cases_a_raw and cases_b_raw:
        map_a = {(cid, cat): p for cid, cat, p in cases_a_raw}
        map_b = {(cid, cat): p for cid, cat, p in cases_b_raw}
        common = set(map_a) & set(map_b)
        regressions = sorted(
            (cid, cat) for cid, cat in common if map_a[(cid, cat)] and not map_b[(cid, cat)]
        )
        improvements = sorted(
            (cid, cat) for cid, cat in common if not map_a[(cid, cat)] and map_b[(cid, cat)]
        )

        col_reg, col_imp = st.columns(2)
        with col_reg:
            st.markdown(
                f'<span style="color:{_FAIL_COLOR};font-weight:bold">'
                f"Regressions (pass→fail): {len(regressions)}</span>",
                unsafe_allow_html=True,
            )
            if regressions:
                st.dataframe(
                    pd.DataFrame(regressions, columns=["Case ID", "Category"]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("None")
        with col_imp:
            st.markdown(
                f'<span style="color:{_PASS_COLOR};font-weight:bold">'
                f"Improvements (fail→pass): {len(improvements)}</span>",
                unsafe_allow_html=True,
            )
            if improvements:
                st.dataframe(
                    pd.DataFrame(improvements, columns=["Case ID", "Category"]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("None")
    else:
        st.caption("Per-case flip data not available for one or both selected runs.")


def _render_solution_rollup(sol: DashSolutionResult) -> None:
    """Render L2 solution-level scores alongside per-agent L1 scores."""
    import pandas as pd

    st.divider()
    overall_color = _PASS_COLOR if sol.passed else _FAIL_COLOR
    overall_label = "✓ PASSED" if sol.passed else "✗ FAILED"

    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.subheader(f"Solution Rollup: `{sol.solution}`")
        st.caption(f"**Run:** {sol.run_at[:19].replace('T', ' ')}")
    with col_status:
        st.markdown(
            f"""
            <div style="
                background:{overall_color}22;
                border:2px solid {overall_color};
                border-radius:8px;
                padding:12px;
                text-align:center;
                font-weight:bold;
                color:{overall_color};
                margin-top:12px;
            ">{overall_label}</div>
            """,
            unsafe_allow_html=True,
        )

    seen: set[str] = set()
    all_cats: list[str] = []
    for c in sol.solution_categories:
        if c.category not in seen:
            seen.add(c.category)
            all_cats.append(c.category)

    rows = []
    sol_cat_map = {c.category: c for c in sol.solution_categories}
    sol_row: dict[str, object] = {"Agent": f"★ {sol.solution} (L2 solution)"}
    for cat in all_cats:
        cs = sol_cat_map.get(cat)
        sol_row[cat.capitalize()] = (
            (("✓ " if cs.met_threshold else "✗ ") + _pct(cs.pass_rate)) if cs else "—"
        )
    rows.append(sol_row)

    for ar in sol.agent_rollups:
        agent_cat_map = {c.category: c for c in ar.categories}
        row: dict[str, object] = {"Agent": ar.agent}
        for cat in all_cats:
            cs = agent_cat_map.get(cat)
            row[cat.capitalize()] = (
                (("✓ " if cs.met_threshold else "✗ ") + _pct(cs.pass_rate)) if cs else "—"
            )
        rows.append(row)

    df = pd.DataFrame(rows)
    cat_cols = [c.capitalize() for c in all_cats]

    def _color_cat(val: object) -> str:
        if isinstance(val, str) and val.startswith("✗"):
            return f"color: {_FAIL_COLOR}"
        if isinstance(val, str) and val.startswith("✓"):
            return f"color: {_PASS_COLOR}"
        return ""

    def _color_agent(val: object) -> str:
        return "font-weight: bold" if isinstance(val, str) and val.startswith("★") else ""

    styled = df.style.map(_color_agent, subset=["Agent"])
    if cat_cols:
        styled = styled.map(_color_cat, subset=cat_cols)

    st.dataframe(styled, use_container_width=True, hide_index=True)


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
        _render_delta_view(results.agent, db_path)

    sol_path = _resolve_solution_path()
    if sol_path is not None:
        try:
            sol = load_solution_results(sol_path)
            _render_solution_rollup(sol)
        except (ValueError, KeyError) as exc:
            st.warning(f"Could not load solution results: {exc}")


main()
