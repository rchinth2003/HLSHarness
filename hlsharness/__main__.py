"""CLI entrypoint for the HLS evaluation harness.

Usage
-----
    hls-eval [--cases PATH] [--agent NAME] [--out PATH]
    hls-eval onboard --spec PATH [--agent NAME] [--cases PATH]
    hls-eval onboard --generate --agent NAME [--cases PATH] [--count N]

Exit codes
----------
0   Success (eval passed / onboard complete).
1   One or more eval categories failed threshold gate.
2   Bad arguments or no cases found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

_console = Console()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hls-eval",
        description="Run the HLS agent evaluation harness against real cases.",
    )
    p.add_argument(
        "--cases",
        default="cases",
        metavar="PATH",
        help="Root directory containing YAML test cases (default: cases/)",
    )
    p.add_argument(
        "--agent",
        default="scheduling-v1",
        metavar="NAME",
        help="Agent adapter name to evaluate (default: scheduling-v1)",
    )
    p.add_argument(
        "--out",
        default="results.json",
        metavar="PATH",
        help="Path to write results.json (default: results.json)",
    )
    p.add_argument(
        "--pdf",
        default=None,
        metavar="PATH",
        help="If set, write a branded PDF Evaluation Report to this path after the run.",
    )
    return p


def _build_onboard_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hls-eval onboard",
        description="Onboard a new agent: interpret spec → manifest, scaffold adapter, generate cases.",
    )
    p.add_argument(
        "--spec",
        metavar="PATH",
        default=None,
        help="Path to an agent spec file (OpenAPI JSON/YAML, system prompt, or plain English). "
        "Writes cases/{agent}/manifest.yaml.",
    )
    p.add_argument(
        "--generate",
        action="store_true",
        help="Read cases/{agent}/manifest.yaml and write adapter stub + YAML cases.",
    )
    p.add_argument(
        "--agent",
        metavar="NAME",
        default=None,
        help="Agent name slug (e.g. prior-auth-v1). Required for --generate; "
        "overrides the agent name inferred from the spec when using --spec.",
    )
    p.add_argument(
        "--cases",
        default="cases",
        metavar="PATH",
        help="Root cases directory (default: cases/)",
    )
    p.add_argument(
        "--count",
        type=int,
        default=3,
        metavar="N",
        help="Number of cases to generate per category (default: 3)",
    )
    return p


def _print_summary(results: object) -> None:  # pragma: no cover
    from hlsharness.results import CategorySummary, EvalResults

    assert isinstance(results, EvalResults)

    table = Table(title=f"HLS Eval — {results.agent}", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Cases", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Pass rate", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Gate", justify="center")

    for cat in results.categories:
        assert isinstance(cat, CategorySummary)
        gate = "[green]PASS[/green]" if cat.met_threshold else "[red]FAIL[/red]"
        table.add_row(
            cat.category,
            str(cat.total),
            str(cat.passed_count),
            f"{cat.pass_rate:.0%}",
            f"{cat.threshold:.0%}",
            gate,
        )

    _console.print()
    _console.print(table)
    overall = "[green]PASSED[/green]" if results.passed else "[red]FAILED[/red]"
    _console.print(f"\n[bold]Overall:[/bold] {overall}\n")


def _run_onboard(argv: list[str]) -> int:  # pragma: no cover
    """Dispatch hls-eval onboard sub-commands."""
    import dataclasses

    from hlsharness.adapter_scaffolder import AdapterScaffolder
    from hlsharness.generator import CaseGenerator
    from hlsharness.manifest import AgentManifest
    from hlsharness.spec_interpreter import SpecInterpreter

    args = _build_onboard_parser().parse_args(argv)

    if not args.spec and not args.generate:
        _console.print("[red]Error:[/red] provide --spec PATH or --generate")
        return 2

    if args.spec and args.generate:
        _console.print("[red]Error:[/red] --spec and --generate are mutually exclusive")
        return 2

    cases_path = Path(args.cases)

    # ── Phase 1: spec → manifest ──────────────────────────────────────────────
    if args.spec:
        try:
            from hlsharness.pdf_extractor import PdfExtractor

            spec_text = PdfExtractor().extract(Path(args.spec))
        except OSError as exc:
            _console.print(f"[red]Error reading spec:[/red] {exc}")
            return 2

        try:
            manifest = SpecInterpreter().interpret(spec_text)
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[red]Error interpreting spec:[/red] {exc}")
            return 2

        if args.agent:
            manifest = dataclasses.replace(manifest, agent=args.agent)

        manifest_path = cases_path / manifest.agent / "manifest.yaml"
        manifest.write(manifest_path)
        _console.print(f"[green]Manifest written:[/green] {manifest_path}")
        return 0

    # ── Phase 2: manifest → adapter stub + cases ──────────────────────────────
    if not args.agent:
        _console.print("[red]Error:[/red] --agent NAME is required with --generate")
        return 2

    manifest_path = cases_path / args.agent / "manifest.yaml"
    try:
        manifest = AgentManifest.load(manifest_path)
    except FileNotFoundError:
        _console.print(
            f"[red]Error:[/red] no manifest found at {manifest_path}. "
            "Run 'hls-eval onboard --spec PATH --agent NAME' first."
        )
        return 2

    stub = AdapterScaffolder().scaffold(manifest)
    agent_slug = manifest.agent.replace("-", "_")
    adapter_path = Path("hlsharness/adapters") / f"{agent_slug}.py"
    adapter_path.parent.mkdir(parents=True, exist_ok=True)
    adapter_path.write_text(stub, encoding="utf-8")
    _console.print(f"[green]Adapter stub written:[/green] {adapter_path}")

    tool_names = [t.name for t in manifest.tools]
    generator = CaseGenerator(
        agent=manifest.agent,
        output_dir=cases_path,
        tools=tool_names,
        agent_description=manifest.description,
    )
    for category in manifest.categories:
        written = generator.generate(category=category, count=args.count)
        for p in written:
            _console.print(f"[green]Case written:[/green] {p}")

    return 0


def _write_pdf_report(results: object, path: Path) -> None:  # pragma: no cover
    from hlsharness.report_config import ReportConfig
    from hlsharness.report_renderer import ReportRenderer
    from hlsharness.results import EvalResults

    assert isinstance(results, EvalResults)
    config_path = Path("report_config.yaml")
    config = ReportConfig.load(config_path) if config_path.exists() else ReportConfig.defaults()
    pdf_bytes = ReportRenderer().render(results, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    _console.print(f"PDF report written to [bold]{path}[/bold]")


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "onboard":
        return _run_onboard(argv[1:])

    args = _build_parser().parse_args(argv)

    try:
        from hlsharness.adapters.scheduling import SchedulingAdapter
        from hlsharness.controller import EvalController
        from hlsharness.judge import Judge

        adapter = SchedulingAdapter()
        judge = Judge()
        controller = EvalController(
            adapter=adapter,
            judge=judge,
            cases_path=Path(args.cases),
        )
        results = controller.run()
    except ValueError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        _console.print(f"[red]Unexpected error:[/red] {exc}")
        return 2

    _print_summary(results)
    results.write_json(Path(args.out))
    _console.print(f"Results written to [bold]{args.out}[/bold]")

    if args.pdf:
        _write_pdf_report(results, Path(args.pdf))

    return 0 if results.passed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
