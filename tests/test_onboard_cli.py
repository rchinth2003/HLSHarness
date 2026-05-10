"""Unit tests for the onboard CLI argument parser — no Azure credentials required."""

from __future__ import annotations

import pytest

from hlsharness.__main__ import _build_onboard_parser


def test_default_cases_path() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "api.yaml"])
    assert args.cases == "cases"


def test_default_count() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "api.yaml"])
    assert args.count == 3


def test_spec_captured() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "openapi.json"])
    assert args.spec == "openapi.json"


def test_generate_flag_default_false() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "api.yaml"])
    assert args.generate is False


def test_generate_flag_set() -> None:
    args = _build_onboard_parser().parse_args(["--generate", "--agent", "prior-auth-v1"])
    assert args.generate is True


def test_agent_override_for_spec() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "api.yaml", "--agent", "my-agent-v1"])
    assert args.agent == "my-agent-v1"


def test_agent_required_for_generate() -> None:
    args = _build_onboard_parser().parse_args(["--generate", "--agent", "prior-auth-v1"])
    assert args.agent == "prior-auth-v1"


def test_agent_default_is_none() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "api.yaml"])
    assert args.agent is None


def test_custom_cases_path() -> None:
    args = _build_onboard_parser().parse_args(["--spec", "api.yaml", "--cases", "/tmp/cases"])
    assert args.cases == "/tmp/cases"


def test_custom_count() -> None:
    args = _build_onboard_parser().parse_args(["--generate", "--agent", "x-v1", "--count", "5"])
    assert args.count == 5


def test_unknown_flag_raises_system_exit() -> None:
    with pytest.raises(SystemExit):
        _build_onboard_parser().parse_args(["--unknown-flag"])
