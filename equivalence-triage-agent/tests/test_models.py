from __future__ import annotations

import pytest
from pydantic import ValidationError

from eq_triage.models import (
    CauseCategory,
    CexVector,
    ConfigDelta,
    LikelyCause,
    MismatchPoint,
    SourceLocation,
)


def test_extra_keys_rejected():
    with pytest.raises(ValidationError):
        SourceLocation.model_validate(
            {"file": "a.v", "line": 1, "col": 1, "bogus": 2}
        )


def test_cex_vector_differs():
    assert CexVector(signal="s", time=0, ref_value="1", rev_value="0").differs
    assert not CexVector(signal="s", time=0, ref_value="1", rev_value="1").differs
    assert not CexVector(signal="s", time=0, ref_value="1").differs


def test_config_delta_differs():
    assert ConfigDelta(key="k", reference_value="a", revised_value="b").differs
    assert not ConfigDelta(key="k", reference_value="a", revised_value="a").differs


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        LikelyCause(category=CauseCategory.WIDTH, confidence=1.5)


def test_line_must_be_positive():
    with pytest.raises(ValidationError):
        SourceLocation(file="a.v", line=0)


def test_mismatch_diff_signals_dedup():
    mp = MismatchPoint(name="x")
    assert mp.fanin_signals == []
