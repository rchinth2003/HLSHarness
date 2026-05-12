<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **HLSHarness** (1886 symbols, 3840 relationships, 40 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> **After every merged PR:** run `gitnexus analyze` in the repo root to keep the index current. Takes ~10 seconds.

## Always Do

- **MUST run impact analysis before editing any symbol.** Run `gitnexus impact "<symbolName>" --direction upstream` via Bash and evaluate the result.
- **MUST run `gitnexus detect-changes` before committing** to verify changes only affect expected symbols and execution flows.
- When exploring unfamiliar code, use `gitnexus query "<concept>"` via Bash to find execution flows instead of grepping.
- When you need full context on a specific symbol — callers, callees, execution flows — run `gitnexus context "<symbolName>"` via Bash.

## Reporting Contract (agreed with user)

Run impact analysis on every edit, but **only report to the user** when ANY of these is true:

1. `risk` is MEDIUM, HIGH, or CRITICAL
2. Symbol participates in 2+ execution flows (`processes_affected >= 2`)
3. Symbol is in the high-impact set: `BaseScorer`, `EvalController`, `JudgeResult`, `CaseResult`, `SolutionController`

> **Note:** Python dynamic dispatch (polymorphism) is a known blind spot — gitnexus cannot trace virtual method calls through subclasses. Always treat the above high-impact set as HIGH risk regardless of what the graph reports.

For LOW-risk leaf symbols not in the above set: run silently, do not narrate.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus rename` which understands the call graph.
- NEVER commit changes without running `gitnexus detect-changes` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/HLSHarness/context` | Codebase overview, check index freshness |
| `gitnexus://repo/HLSHarness/clusters` | All functional areas |
| `gitnexus://repo/HLSHarness/processes` | All execution flows |
| `gitnexus://repo/HLSHarness/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->