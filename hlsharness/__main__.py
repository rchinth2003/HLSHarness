"""CLI entrypoint for the HLS evaluation harness.

Usage
-----
    uv run python -m hlsharness [--cases PATH] [--agent NAME] [--out PATH]
    hls-eval [--cases PATH] [--agent NAME] [--out PATH]

Exit codes
----------
0   All categories met their pass-rate thresholds.
1   One or more categories failed (threshold gate triggered).
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


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
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

    return 0 if results.passed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
