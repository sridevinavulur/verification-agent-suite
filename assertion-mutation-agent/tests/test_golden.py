"""Golden-output test: the counter benchmark must produce a stable report."""

import json
import pathlib

from assertion_mutation_agent.agent import run_mutation_analysis

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
GOLDEN = ROOT / "tests" / "golden" / "counter_mutation_report.json"


def _run_counter():
    rtl = (EXAMPLES / "counter.v").read_text(encoding="utf-8")
    sva_path = EXAMPLES / "counter.sva"
    report = run_mutation_analysis(
        module="counter",
        rtl_source=rtl,
        rtl_file=str(EXAMPLES / "counter.v"),
        property_texts={str(sva_path): sva_path.read_text(encoding="utf-8")},
    )
    return report


def test_counter_matches_golden():
    report = _run_counter()
    got = report.model_dump(mode="json")
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))

    # Compare the deterministic, content-derived parts of the report.
    assert got["score"] == want["score"]
    assert got["surviving_by_operator"] == want["surviving_by_operator"]
    assert [m["mutant_id"] for m in got["surviving_mutants"]] == [
        m["mutant_id"] for m in want["surviving_mutants"]
    ]
    assert [r["mutant_id"] for r in got["results"]] == [
        r["mutant_id"] for r in want["results"]
    ]
    assert [r["status"] for r in got["results"]] == [
        r["status"] for r in want["results"]
    ]


def test_counter_score_is_reproducible():
    a = _run_counter().model_dump(mode="json")
    b = _run_counter().model_dump(mode="json")
    assert a == b


def test_counter_survivors_are_uncovered_signals():
    report = _run_counter()
    # Every survivor is a counter-module mutant that no property caught.
    for sm in report.surviving_mutants:
        assert sm.mutant_id.startswith("counter.")
    # Score must exclude invalid + inconclusive (none here), so scored==total.
    s = report.score
    assert s.scored == s.total == s.detected + s.survived
