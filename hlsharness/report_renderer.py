"""ReportRenderer — generate a branded PDF Evaluation Report from EvalResults.

``render()`` is the only public method and is marked ``# pragma: no cover``
because it imports weasyprint (requires system libraries) at call time.
Unit tests exercise ``_build_html()`` directly — pure string generation,
no system dependencies required.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hlsharness.report_config import ReportConfig
from hlsharness.results import CaseResult, EvalResults

_CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Inter, sans-serif; font-size: 11pt; color: #1a1a1a; }}

/* ── cover ── */
.cover {{
    height: 100vh; display: flex; flex-direction: column;
    justify-content: center; align-items: flex-start;
    padding: 80px; background: {brand_color};
}}
.cover h1 {{ font-size: 28pt; color: #fff; font-weight: 700; margin-bottom: 12px; }}
.cover .subtitle {{ font-size: 14pt; color: rgba(255,255,255,0.8); margin-bottom: 32px; }}
.cover .verdict {{
    display: inline-block; padding: 10px 24px; border-radius: 4px;
    font-size: 16pt; font-weight: 700; color: #fff;
    background: rgba(255,255,255,0.2);
}}
.cover .verdict.passed {{ background: #22c55e; }}
.cover .verdict.failed {{ background: #ef4444; }}

/* ── content pages ── */
.page {{ padding: 48px 64px; page-break-before: always; }}
h2 {{ font-size: 18pt; font-weight: 700; color: {brand_color}; margin-bottom: 20px; }}
h3 {{ font-size: 13pt; font-weight: 600; margin: 24px 0 10px; }}

/* ── scorecard table ── */
table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
th {{ background: {brand_color}; color: #fff; padding: 8px 12px; text-align: left; font-weight: 600; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }}
tr:nth-child(even) td {{ background: #f9fafb; }}
.gate-pass {{ color: #16a34a; font-weight: 700; }}
.gate-fail {{ color: #dc2626; font-weight: 700; }}

/* ── case cards ── */
.case-card {{
    border: 1px solid #e5e7eb; border-radius: 6px;
    padding: 14px 18px; margin-bottom: 14px;
}}
.case-card.failed {{ border-left: 4px solid #ef4444; }}
.case-card.passed {{ border-left: 4px solid #22c55e; }}
.case-header {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
.case-id {{ font-weight: 600; }}
.case-score {{ font-weight: 600; color: {brand_color}; }}
.case-category {{ font-size: 9pt; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }}
.case-input {{ font-style: italic; color: #374151; margin: 6px 0; font-size: 10pt; }}
.case-rationale {{ color: #4b5563; font-size: 10pt; }}

/* ── footer ── */
@page {{ margin: 0; }}
"""


class ReportRenderer:
    """Generates a branded PDF Evaluation Report from an ``EvalResults`` object.

    Usage
    -----
    ::

        renderer = ReportRenderer()
        pdf_bytes = renderer.render(results, config)
        Path("report.pdf").write_bytes(pdf_bytes)
    """

    def render(
        self,
        results: EvalResults,
        config: ReportConfig,
        baseline_note: str | None = None,
    ) -> bytes:  # pragma: no cover
        """Return PDF bytes for *results* styled with *config*.

        Imports ``weasyprint`` lazily so the module can be imported in test
        environments where weasyprint's system libraries are unavailable.
        """
        from weasyprint import HTML  # noqa: PLC0415

        date = datetime.now(UTC).strftime("%Y-%m-%d")
        html = self._build_html(results, config, date, baseline_note=baseline_note)
        return HTML(string=html).write_pdf()  # type: ignore[no-any-return]

    # ── internal ──────────────────────────────────────────────────────────────

    def _build_html(
        self,
        results: EvalResults,
        config: ReportConfig,
        date: str,
        baseline_note: str | None = None,
    ) -> str:
        """Return the full HTML document as a string.

        Pure function — no I/O, no external dependencies.  Tested directly.
        """
        css = _CSS.format(brand_color=config.brand_color)
        title = config.render_title(agent=results.agent, date=date)
        verdict_cls = "passed" if results.passed else "failed"
        verdict_label = "PASSED" if results.passed else "FAILED"

        baseline_note_html = (
            f'<div class="baseline-note">{baseline_note}</div>' if baseline_note else ""
        )
        cover = (
            f'<div class="cover">'
            f'<div class="subtitle">{config.org}</div>'
            f"<h1>{title}</h1>"
            f'<div class="subtitle">{date}</div>'
            f'<div class="verdict {verdict_cls}">{verdict_label}</div>'
            f"{baseline_note_html}"
            f"</div>"
        )

        scorecard = self._build_scorecard(results)
        failed_section = self._build_case_section(
            [c for c in results.cases if not c.passed], "Failed Cases", "failed"
        )
        passed_section = self._build_case_section(
            [c for c in results.cases if c.passed], "Passing Cases", "passed"
        )

        body = f"{cover}{scorecard}{failed_section}{passed_section}"
        return f"<!DOCTYPE html><html><head><style>{css}</style></head><body>{body}</body></html>"

    @staticmethod
    def _build_scorecard(results: EvalResults) -> str:
        has_delta = any(c.delta_vs_baseline is not None for c in results.categories)
        rows = ""
        for cat in results.categories:
            gate_cls = "gate-pass" if cat.met_threshold else "gate-fail"
            gate_label = "PASS" if cat.met_threshold else "FAIL"
            delta_cell = ""
            if has_delta:
                if cat.delta_vs_baseline is not None:
                    sign = "+" if cat.delta_vs_baseline >= 0 else ""
                    colour = "#16a34a" if cat.delta_vs_baseline >= 0 else "#dc2626"
                    delta_cell = (
                        f'<td style="color:{colour};font-weight:700">'
                        f"{sign}{cat.delta_vs_baseline:.0%}</td>"
                    )
                else:
                    delta_cell = "<td>—</td>"
            rows += (
                f"<tr>"
                f"<td>{cat.category}</td>"
                f"<td>{cat.total}</td>"
                f"<td>{cat.passed_count}</td>"
                f"<td>{cat.pass_rate:.0%}</td>"
                f"<td>{cat.threshold:.0%}</td>"
                f"{delta_cell}"
                f'<td class="{gate_cls}">{gate_label}</td>'
                f"</tr>"
            )
        delta_header = "<th>Delta</th>" if has_delta else ""
        table = (
            "<table>"
            "<tr><th>Category</th><th>Cases</th><th>Passed</th>"
            f"<th>Pass rate</th><th>Threshold</th>{delta_header}<th>Gate</th></tr>"
            f"{rows}</table>"
        )
        return f'<div class="page"><h2>Scorecard</h2>{table}</div>'

    @staticmethod
    def _build_case_section(cases: list[CaseResult], title: str, css_class: str) -> str:
        if not cases:
            return ""
        cards = ""
        for c in cases:
            cards += (
                f'<div class="case-card {css_class}">'
                f'<div class="case-header">'
                f'<span class="case-id">{c.case_id}</span>'
                f'<span class="case-score">Score: {c.score:.2f}</span>'
                f"</div>"
                f'<div class="case-category">{c.category}</div>'
                f'<div class="case-input">"{c.input_summary}"</div>'
                f'<div class="case-rationale">{c.rationale}</div>'
                f"</div>"
            )
        return f'<div class="page"><h2>{title}</h2>{cards}</div>'
