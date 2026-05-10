"""Unit tests for the __main__ CLI argument parser — no Azure credentials required."""

from __future__ import annotations

import pytest

from hlsharness.__main__ import _build_parser


def test_default_cases_path() -> None:
    args = _build_parser().parse_args([])
    assert args.cases == "cases"


def test_default_agent() -> None:
    args = _build_parser().parse_args([])
    assert args.agent == "scheduling-v1"


def test_default_out() -> None:
    args = _build_parser().parse_args([])
    assert args.out == "results.json"


def test_custom_cases_path() -> None:
    args = _build_parser().parse_args(["--cases", "/tmp/my-cases"])
    assert args.cases == "/tmp/my-cases"


def test_custom_agent() -> None:
    args = _build_parser().parse_args(["--agent", "prior-auth-v2"])
    assert args.agent == "prior-auth-v2"


def test_custom_out() -> None:
    args = _build_parser().parse_args(["--out", "artifacts/results.json"])
    assert args.out == "artifacts/results.json"


def test_unknown_flag_raises_system_exit() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--unknown-flag"])
