from assertion_mutation_agent.agent import compute_score
from assertion_mutation_agent.executor import MockExecutor, get_executor
from assertion_mutation_agent.models import (
    Mutant,
    MutantResult,
    MutantStatus,
    MutationOperator,
    PropertyRef,
    SourceDiff,
    SourceLocation,
)


def _mutant(signals, mutated="X = 1;", src="X = 0;"):
    diff = SourceDiff(
        location=SourceLocation(file="m", line=1, col_start=1, col_end=1),
        original_text="0",
        mutated_text="1",
        original_line=src,
        mutated_line=mutated,
    )
    return Mutant(
        mutant_id="m.relational_flip.1.deadbeef",
        operator=MutationOperator.RELATIONAL_FLIP,
        description="test",
        diff=diff,
        mutated_signals=signals,
        mutated_source=mutated,
    )


def test_detected_when_property_references_signal():
    ex = MockExecutor()
    m = _mutant(["count"])
    props = [PropertyRef(name="p", text="", referenced_signals=["count", "clk"])]
    r = ex.classify(m, "X = 0;", props)
    assert r.status == MutantStatus.DETECTED
    assert r.detected_by == ["p"]


def test_survived_when_no_property_references_signal():
    ex = MockExecutor()
    m = _mutant(["load_val"])
    props = [PropertyRef(name="p", text="", referenced_signals=["count"])]
    r = ex.classify(m, "X = 0;", props)
    assert r.status == MutantStatus.SURVIVED


def test_invalid_when_source_unchanged():
    ex = MockExecutor()
    m = _mutant(["count"], mutated="X = 0;", src="X = 0;")
    props = [PropertyRef(name="p", text="", referenced_signals=["count"])]
    r = ex.classify(m, "X = 0;", props)
    assert r.status == MutantStatus.INVALID


def test_inconclusive_when_no_signals():
    ex = MockExecutor()
    m = _mutant([])
    props = [PropertyRef(name="p", text="", referenced_signals=["count"])]
    r = ex.classify(m, "X = 0;", props)
    assert r.status == MutantStatus.INCONCLUSIVE


def test_get_executor_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        get_executor("verilator-formal")


def _res(status):
    return MutantResult(
        mutant_id="x",
        operator=MutationOperator.RELATIONAL_FLIP,
        status=status,
    )


def test_score_excludes_invalid_and_inconclusive():
    results = [
        _res(MutantStatus.DETECTED),
        _res(MutantStatus.DETECTED),
        _res(MutantStatus.SURVIVED),
        _res(MutantStatus.INVALID),
        _res(MutantStatus.INCONCLUSIVE),
    ]
    s = compute_score(results)
    assert s.total == 5
    assert s.scored == 3  # 2 detected + 1 survived; invalid+inconclusive excluded
    assert s.mutation_score == round(2 / 3, 6)


def test_score_timeout_and_error_not_pass():
    results = [
        _res(MutantStatus.DETECTED),
        _res(MutantStatus.TIMEOUT),
        _res(MutantStatus.ERROR),
    ]
    s = compute_score(results)
    # timeout/error are not detected and not in the scored denominator.
    assert s.detected == 1
    assert s.scored == 1
    assert s.mutation_score == 1.0
    assert s.timeout == 1 and s.error == 1


def test_score_zero_scored_is_zero():
    s = compute_score([_res(MutantStatus.INVALID)])
    assert s.mutation_score == 0.0 and s.scored == 0
