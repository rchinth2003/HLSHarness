"""Unit tests for MetricCollector — no Azure credentials required."""

import pytest

from hlsharness.metrics import MetricCollector


def test_record_and_get():
    col = MetricCollector()
    col.record("TC-001", latency_ms=1500.0, prompt_tokens=400, completion_tokens=120)
    m = col.get("TC-001")
    assert m.latency_ms == 1500.0
    assert m.prompt_tokens == 400
    assert m.completion_tokens == 120


def test_total_tokens():
    col = MetricCollector()
    col.record("TC-001", latency_ms=100.0, prompt_tokens=200, completion_tokens=50)
    assert col.get("TC-001").total_tokens == 250


def test_aggregate_total_tokens():
    col = MetricCollector()
    col.record("TC-001", latency_ms=100.0, prompt_tokens=200, completion_tokens=50)
    col.record("TC-002", latency_ms=200.0, prompt_tokens=300, completion_tokens=80)
    assert col.total_tokens() == 630


def test_average_latency():
    col = MetricCollector()
    col.record("TC-001", latency_ms=1000.0, prompt_tokens=0, completion_tokens=0)
    col.record("TC-002", latency_ms=3000.0, prompt_tokens=0, completion_tokens=0)
    assert col.average_latency_ms() == 2000.0


def test_average_latency_empty():
    assert MetricCollector().average_latency_ms() == 0.0


def test_get_unknown_case_raises():
    with pytest.raises(KeyError, match="TC-999"):
        MetricCollector().get("TC-999")


def test_all_returns_copy():
    col = MetricCollector()
    col.record("TC-001", latency_ms=100.0, prompt_tokens=10, completion_tokens=5)
    snapshot = col.all()
    snapshot.clear()
    assert len(col.all()) == 1


def test_latency_rounded_to_one_decimal():
    col = MetricCollector()
    col.record("TC-001", latency_ms=123.456789, prompt_tokens=0, completion_tokens=0)
    assert col.get("TC-001").latency_ms == 123.5
