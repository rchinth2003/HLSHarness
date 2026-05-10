"""MetricCollector — records latency and token usage per case.

Pure Python, no Azure calls. Safe to use in unit tests without credentials.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaseMetrics:
    """Operational metrics for a single case run.

    Parameters
    ----------
    latency_ms:        Wall-clock time for the full agent run in milliseconds.
    prompt_tokens:     Tokens consumed on the prompt side across all LLM calls.
    completion_tokens: Tokens generated across all LLM calls.
    """

    latency_ms: float
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        """Sum of prompt and completion tokens."""
        return self.prompt_tokens + self.completion_tokens


class MetricCollector:
    """Accumulates per-case operational metrics during an eval run.

    Examples
    --------
    >>> collector = MetricCollector()
    >>> collector.record("TC-001", latency_ms=1234.5, prompt_tokens=400, completion_tokens=120)
    >>> collector.get("TC-001").total_tokens
    520
    """

    def __init__(self) -> None:
        self._records: dict[str, CaseMetrics] = {}

    def record(
        self,
        case_id: str,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record metrics for a case. Overwrites any prior entry for the same ID."""
        self._records[case_id] = CaseMetrics(
            latency_ms=round(latency_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def get(self, case_id: str) -> CaseMetrics:
        """Return metrics for a specific case.

        Raises
        ------
        KeyError
            If ``case_id`` has not been recorded yet.
        """
        if case_id not in self._records:
            raise KeyError(f"No metrics recorded for case '{case_id}'")
        return self._records[case_id]

    def all(self) -> dict[str, CaseMetrics]:
        """Return a copy of all recorded metrics keyed by case ID."""
        return dict(self._records)

    def total_tokens(self) -> int:
        """Sum of all token usage across every recorded case."""
        return sum(m.total_tokens for m in self._records.values())

    def average_latency_ms(self) -> float:
        """Mean latency across all recorded cases. Returns 0.0 if empty."""
        if not self._records:
            return 0.0
        return sum(m.latency_ms for m in self._records.values()) / len(self._records)
