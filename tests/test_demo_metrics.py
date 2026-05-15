import yaml
from pathlib import Path

_METRICS_PATH = Path(__file__).parent.parent / "demo" / "metrics.yaml"


def test_metrics_yaml_exists():
    assert _METRICS_PATH.exists()


def test_metrics_yaml_has_disclaimer_and_four_metrics():
    data = yaml.safe_load(_METRICS_PATH.read_text(encoding="utf-8"))
    assert "disclaimer" in data
    assert len(data["metrics"]) == 4
    for m in data["metrics"]:
        assert {"name", "baseline", "agentic"} <= set(m.keys())
