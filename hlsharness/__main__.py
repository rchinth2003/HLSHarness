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
3   Eval passed absolute thresholds but regressed vs. baseline.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from hlsharness.results import CategorySummary

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
        help="If provided, write a branded PDF evaluation report to this path.",
    )
    p.add_argument(
        "--baseline",
        action="store_true",
        default=False,
        help="Compare run against stored baseline; exit 3 on regression.",
    )
    p.add_argument(
        "--db",
        default=".hls_runs.db",
        metavar="PATH",
        help="Path to the RunStore SQLite database (default: .hls_runs.db).",
    )
    p.add_argument(
        "--version",
        default="",
        metavar="VERSION",
        help="Agent version string stored alongside the run (default: '').",
    )
    p.add_argument(
        "--solution",
        default=None,
        metavar="NAME",
        help=(
            "Run solution eval: load cases/{NAME}/solution.yaml and evaluate "
            "all declared agents via SolutionController. Writes solution_results.json."
        ),
    )
    return p


def _build_onboard_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hls-eval onboard",
        description="Onboard a new agent: interpret spec → agent.yaml, scaffold adapter, generate cases.",
    )
    p.add_argument(
        "--spec",
        metavar="PATH",
        default=None,
        help="Path to an agent spec file (OpenAPI JSON/YAML, system prompt, or plain English). "
        "Writes cases/{agent}/agent.yaml and prints a behavioral critique.",
    )
    p.add_argument(
        "--critique",
        metavar="PATH",
        default=None,
        help="Path to an existing agent.yaml to re-run the behavioral critique without Phase 1.",
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
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt and automatically chain Phase 1 (spec → agent.yaml) "
        "into Phase 2 (case generation) in a single command.",
    )
    return p


def _apply_baseline_deltas(
    categories: list[CategorySummary],
    baseline_categories: list[CategorySummary],
) -> list[CategorySummary]:
    """Return a new list of CategorySummary with delta_vs_baseline populated.

    Each category's delta = current pass_rate − baseline pass_rate.
    Categories absent from the baseline are left with delta_vs_baseline=None.
    """
    baseline_by_cat = {c.category: c.pass_rate for c in baseline_categories}
    result = []
    for cat in categories:
        if cat.category in baseline_by_cat:
            delta = cat.pass_rate - baseline_by_cat[cat.category]
            result.append(dataclasses.replace(cat, delta_vs_baseline=delta))
        else:
            result.append(cat)
    return result


def _compute_exit_code(results: object, delta_thresholds: dict[str, float]) -> int:
    """Return the appropriate CLI exit code for a completed eval run.

    Returns
    -------
    0   All categories met their absolute threshold and no delta gate fired.
    1   At least one category failed its absolute pass-rate threshold.
    3   All absolute thresholds passed but a category regressed beyond its
        delta_threshold.  Only categories listed in *delta_thresholds* are
        checked; absence means no delta gate for that category.
    """
    from hlsharness.results import EvalResults

    assert isinstance(results, EvalResults)
    if not results.passed:
        return 1
    for cat in results.categories:
        if cat.delta_vs_baseline is not None and cat.category in delta_thresholds:
            allowed_drop = delta_thresholds[cat.category]
            if cat.delta_vs_baseline < -allowed_drop:
                return 3
    return 0


def _print_summary(results: object) -> None:  # pragma: no cover
    from hlsharness.results import CategorySummary, EvalResults

    assert isinstance(results, EvalResults)

    has_delta = any(c.delta_vs_baseline is not None for c in results.categories)

    table = Table(title=f"HLS Eval — {results.agent}", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Cases", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Pass rate", justify="right")
    table.add_column("Threshold", justify="right")
    if has_delta:
        table.add_column("Delta", justify="right")
    table.add_column("Gate", justify="center")

    for cat in results.categories:
        assert isinstance(cat, CategorySummary)
        gate = "[green]PASS[/green]" if cat.met_threshold else "[red]FAIL[/red]"
        row = [
            cat.category,
            str(cat.total),
            str(cat.passed_count),
            f"{cat.pass_rate:.0%}",
            f"{cat.threshold:.0%}",
        ]
        if has_delta:
            if cat.delta_vs_baseline is not None:
                sign = "+" if cat.delta_vs_baseline >= 0 else ""
                colour = "green" if cat.delta_vs_baseline >= 0 else "red"
                row.append(f"[{colour}]{sign}{cat.delta_vs_baseline:.0%}[/{colour}]")
            else:
                row.append("—")
        row.append(gate)
        table.add_row(*row)

    _console.print()
    _console.print(table)
    overall = "[green]PASSED[/green]" if results.passed else "[red]FAILED[/red]"
    _console.print(f"\n[bold]Overall:[/bold] {overall}\n")


def _run_onboard(argv: list[str]) -> int:  # pragma: no cover
    """Dispatch hls-eval onboard sub-commands."""
    import dataclasses

    import yaml
    from rich.syntax import Syntax

    from hlsharness.maf_agent import load_agent_yaml
    from hlsharness.spec_interpreter import SpecInterpreter

    args = _build_onboard_parser().parse_args(argv)

    if not args.spec and not args.generate and not args.critique:
        _console.print("[red]Error:[/red] provide --spec PATH, --critique PATH, or --generate")
        return 2

    if args.spec and args.generate:
        _console.print("[red]Error:[/red] --spec and --generate are mutually exclusive")
        return 2

    cases_path = Path(args.cases)

    # ── Phase 1: spec → agent.yaml ────────────────────────────────────────────
    if args.spec:
        try:
            from hlsharness.pdf_extractor import PdfExtractor

            spec_text = PdfExtractor().extract(Path(args.spec))
        except OSError as exc:
            _console.print(f"[red]Error reading spec:[/red] {exc}")
            return 2

        try:
            interp = SpecInterpreter()
            agent_yaml_obj = interp.interpret(spec_text)
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[red]Error interpreting spec:[/red] {exc}")
            return 2

        if args.agent:
            agent_yaml_obj = dataclasses.replace(agent_yaml_obj, name=args.agent)

        yaml_path = cases_path / agent_yaml_obj.name / "agent.yaml"
        agent_yaml_obj.write(yaml_path)
        _console.print(f"[green]agent.yaml written:[/green] {yaml_path}")

        yaml_text = yaml.dump(agent_yaml_obj.to_dict(), allow_unicode=True, sort_keys=False)
        _console.print("\n[bold]Draft agent.yaml[/bold]\n")
        _console.print(Syntax(yaml_text, "yaml"))

        # ── Phase 2: behavioral critique ─────────────────────────────────────
        _console.print("\n[bold]Behavioral critique (Phase 2)[/bold]\n")
        try:
            critique = interp.critique(yaml_text)
            _console.print(critique)
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[yellow]Critique unavailable:[/yellow] {exc}")

        # ── Phase 3: case generation ──────────────────────────────────────────
        if not args.yes:
            _console.print(
                "\n[bold]agent.yaml written.[/bold] "
                "Press Enter to generate cases, or Ctrl-C to edit agent.yaml first."
            )
            try:
                input()
            except KeyboardInterrupt:
                _console.print(
                    "\n[yellow]Stopped.[/yellow] "
                    "Edit agent.yaml then re-run with --generate to create cases."
                )
                return 0

        from hlsharness.generator import CaseGenerator

        _stubs_dir = Path("stubs")
        _personas_dir = Path("personas")
        _generator = CaseGenerator(
            agent=agent_yaml_obj.name,
            output_dir=cases_path,
            agent_yaml=agent_yaml_obj,
            stubs_dir=_stubs_dir,
            personas_dir=_personas_dir,
        )
        for p in _generator.generate_fixtures(stubs_dir=_stubs_dir):
            _console.print(f"[green]Fixture written:[/green] {p}")
        for _cat in agent_yaml_obj.x_harness.get("categories", []):
            for p in _generator.generate(category=_cat, count=args.count):
                _console.print(f"[green]Case written:[/green] {p}")

        return 0

    # ── Re-critique only ──────────────────────────────────────────────────────
    if args.critique:
        try:
            agent_yaml_obj = load_agent_yaml(Path(args.critique))
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[red]Error loading agent.yaml:[/red] {exc}")
            return 2

        yaml_text = yaml.dump(agent_yaml_obj.to_dict(), allow_unicode=True, sort_keys=False)
        _console.print("\n[bold]Behavioral critique[/bold]\n")
        try:
            critique = SpecInterpreter().critique(yaml_text)
            _console.print(critique)
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[red]Critique failed:[/red] {exc}")
            return 2
        return 0

    # ── Phase 3: agent.yaml → fixture stubs + cases ──────────────────────────
    if not args.agent:
        _console.print("[red]Error:[/red] --agent NAME is required with --generate")
        return 2

    agent_yaml_path = cases_path / args.agent / "agent.yaml"
    try:
        agent_yaml_obj = load_agent_yaml(agent_yaml_path)
    except FileNotFoundError:
        _console.print(
            f"[red]Error:[/red] no agent.yaml found at {agent_yaml_path}. "
            "Run 'hls-eval onboard --spec PATH --agent NAME' first."
        )
        return 2
    except Exception as exc:  # noqa: BLE001
        _console.print(f"[red]Error loading agent.yaml:[/red] {exc}")
        return 2

    from hlsharness.generator import CaseGenerator

    stubs_dir = Path("stubs")
    personas_dir = Path("personas")

    generator = CaseGenerator(
        agent=agent_yaml_obj.name,
        output_dir=cases_path,
        agent_yaml=agent_yaml_obj,
        stubs_dir=stubs_dir,
        personas_dir=personas_dir,
    )

    # Step 1: generate fixture stubs for every tool
    stubs_written = generator.generate_fixtures(stubs_dir=stubs_dir)
    for p in stubs_written:
        _console.print(f"[green]Fixture written:[/green] {p}")

    # Step 2: generate test cases per category
    categories: list[str] = agent_yaml_obj.x_harness.get("categories", [])
    for category in categories:
        written = generator.generate(category=category, count=args.count)
        for p in written:
            _console.print(f"[green]Case written:[/green] {p}")

    return 0


def _write_pdf_report(
    results: object, path: Path, baseline_note: str | None = None
) -> None:  # pragma: no cover
    from hlsharness.report_config import ReportConfig
    from hlsharness.report_renderer import ReportRenderer
    from hlsharness.results import EvalResults

    assert isinstance(results, EvalResults)
    config = ReportConfig.defaults()
    pdf_bytes = ReportRenderer().render(results, config, baseline_note=baseline_note)
    path.write_bytes(pdf_bytes)
    _console.print(f"PDF report written to [bold]{path}[/bold]")


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "onboard":
        return _run_onboard(argv[1:])

    args = _build_parser().parse_args(argv)

    # ── Solution eval (L2) ────────────────────────────────────────────────────
    if args.solution:
        try:
            from hlsharness.judge import Judge
            from hlsharness.solution_controller import SolutionController
            from hlsharness.solution_manifest import SolutionManifest

            solution_yaml_path = Path(args.cases) / args.solution / "solution.yaml"
            manifest = SolutionManifest.load(solution_yaml_path)
            manifest.validate(cases_path=Path(args.cases))

            solution_ctrl = SolutionController(
                manifest=manifest,
                judge=Judge(),
                cases_path=Path(args.cases),
            )
            solution_result = solution_ctrl.run()
        except ValueError as exc:
            _console.print(f"[red]Error:[/red] {exc}")
            return 2
        except Exception as exc:  # noqa: BLE001
            _console.print(f"[red]Unexpected error:[/red] {exc}")
            return 2

        out_path = Path(args.out).parent / "solution_results.json"
        solution_result.write_json(out_path)
        _console.print(f"Solution results written to [bold]{out_path}[/bold]")
        overall = "[green]PASSED[/green]" if solution_result.passed else "[red]FAILED[/red]"
        _console.print(f"\n[bold]Solution overall:[/bold] {overall}\n")
        return 0 if solution_result.passed else 1

    # ── Single-agent eval (L1) ────────────────────────────────────────────────
    try:
        from hlsharness.controller import EvalController
        from hlsharness.judge import Judge
        from hlsharness.maf_agent import load_agent_yaml
        from hlsharness.run_store import RunStore

        agent_yaml_path = Path(args.cases) / args.agent / "agent.yaml"
        agent_yaml_obj = load_agent_yaml(agent_yaml_path)
        delta_thresholds: dict[str, float] = {
            k: float(v) for k, v in agent_yaml_obj.x_harness.get("delta_thresholds", {}).items()
        }

        judge = Judge()
        controller = EvalController(
            agent_yaml_path=agent_yaml_path,
            judge=judge,
            cases_path=Path(args.cases),
        )
        results = controller.run()

        # Persist to RunStore
        store = RunStore(db_path=Path(args.db))
        store.save(results, version=args.version)

        # Apply baseline deltas if requested
        baseline_note: str | None = None
        if args.baseline:
            baseline = store.load_baseline(results.agent, version=args.version)
            if baseline:
                results = dataclasses.replace(
                    results,
                    categories=_apply_baseline_deltas(results.categories, baseline.categories),
                )
            else:
                baseline_note = "No baseline found — this run establishes the new baseline."
                store.promote_baseline(store.history(results.agent, limit=1)[0].id)

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
        _write_pdf_report(results, Path(args.pdf), baseline_note=baseline_note)

    return _compute_exit_code(results, delta_thresholds)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
