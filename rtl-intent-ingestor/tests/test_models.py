"""Tests that the Pydantic contracts actually validate (not just annotate)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rtl_intent.models import (
    ClockCandidate,
    Port,
    PortDirection,
    SourceLocation,
)


def _loc() -> SourceLocation:
    return SourceLocation(file="t.sv", line=1, col=1, end_line=1, end_col=5)


def test_extra_keys_forbidden() -> None:
    with pytest.raises(ValidationError):
        Port.model_validate(
            {
                "name": "a",
                "direction": "input",
                "location": _loc().model_dump(),
                "bogus": 1,
            }
        )


def test_confidence_must_be_in_range() -> None:
    with pytest.raises(ValidationError):
        ClockCandidate(signal="clk", confidence=1.5, location=_loc())


def test_line_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SourceLocation(file="t.sv", line=0, col=1, end_line=1, end_col=1)


def test_valid_port() -> None:
    p = Port(name="a", direction=PortDirection.INPUT, location=_loc())
    assert p.direction == PortDirection.INPUT
    assert p.net_kind is None
