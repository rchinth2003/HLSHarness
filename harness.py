#!/usr/bin/env python3
"""HLS Evaluation Harness — CLI entry point.

Usage
-----
Run all cases for an agent::

    python harness.py run --agent scheduling-v1

Run only functional cases::

    python harness.py run --agent scheduling-v1 --categories functional

Launch the Streamlit dashboard after the run (Slice 3+)::

    python harness.py run --agent scheduling-v1 --serve

Environment variables required
-------------------------------
AZURE_OPENAI_ENDPOINT
    Full endpoint URL for the ``sow-gen-ai`` Azure OpenAI resource.
    Example: https://sow-gen-ai.openai.azure.com/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

_console = Console()

_ADAPTER_REGISTRY: dict[str, str] = {
    "scheduling-v1": "hlsharness.adapters.scheduling:SchedulingAdapter",
}


def _load_adapter(name: str) -> object:
    """Import and instantiate an adapter by registry name."""
    if name not in _ADAPTER_REGISTRY:
        _console.print(f"[red]Unknown agent:[/red] {name}")
        _console.print(f"Available: {list(_ADAPTER_REGISTRY.keys())}")
        sys.exit(1)
    module_path, class_name = _ADAPTER_REGISTRY[name].split(":")
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the eval run subcommand."""
    from hlsharness.controller import EvalController
    from hlsharness.judge import Judge

    adapter = _load_adapter(args.agent)
    judge = Judge(threshold=args.threshold)

    controller = EvalController(
        adapter=adapter,  # type: ignore[arg-type]
        judge=judge,
        cases_path=Path(args.cases),
    )

    results = controller.run(categories=args.categories or None)

    output_path = Path(args.output)
    results.write_json(output_path)
    _console.print(f"\n[dim]Results written → {output_path}[/dim]")

    table = Table(title="Eval Summary", show_header=True, header_style="bold")
    table.add_column("Category")
    table.add_column("Cases", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Gate")

    for cat in results.categories:
        gate = "[green]PASS[/green]" if cat.met_threshold else "[red]FAIL[/red]"
        table.add_row(
            cat.category,
            str(cat.total),
            str(cat.passed_count),
            f"{cat.pass_rate:.0%}",
            f"{cat.threshold:.0%}",
            gate,
        )

    _console.print(table)
    overall = "[green]✓ PASSED[/green]" if results.passed else "[red]✗ FAILED[/red]"
    _console.print(f"\nOverall: {overall}\n")

    if args.serve:
        _console.print(
            "[yellow]--serve: Streamlit dashboard coming in Slice 3.[/yellow]"
        )

    return 0 if results.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="HLS Agent Evaluation Harness",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run evaluation against an agent")
    run_p.add_argument(
        "--agent", required=True, help="Agent name (e.g. scheduling-v1)"
    )
    run_p.add_argument("--cases", default="cases", help="Path to cases directory")
    run_p.add_argument("--output", default="results.json", help="Output JSON path")
    run_p.add_argument(
        "--threshold", type=float, default=0.8, help="Pass threshold (default 0.8)"
    )
    run_p.add_argument(
        "--categories", nargs="*", help="Limit to specific categories"
    )
    run_p.add_argument(
        "--serve", action="store_true", help="Launch Streamlit after run"
    )

    args = parser.parse_args()
    if args.command == "run":
        return cmd_run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
