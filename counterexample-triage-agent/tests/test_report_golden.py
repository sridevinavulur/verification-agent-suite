"""Golden report-quality tests.

These assert that the deterministic Markdown/JSON reports for the bundled
toy_counter benchmark match checked-in golden files byte-for-byte. If the engine
output changes intentionally, regenerate the goldens with:

    cx-triage demo --narrate --out-md tests/golden/toy_counter_report.md
    cx-triage triage --trace examples/toy_counter/counter_fail.vcd \
        --failure examples/toy_counter/failure.json \
        --manifest examples/toy_counter/manifest.json \
        --out-json tests/golden/toy_counter_report.json
"""

import json

from cx_triage.llm import get_adapter
from cx_triage.models import AssertionFailure, RTLIntentManifest, TriageReport
from cx_triage.parser import parse_vcd_file
from cx_triage.paths import portable_path
from cx_triage.report import render_markdown
from cx_triage.triage import TriageEngine


def _build_report(examples_dir, repo_dir, narrate: bool) -> TriageReport:
    d = examples_dir / "toy_counter"
    trace = parse_vcd_file(d / "counter_fail.vcd")
    failure = AssertionFailure.model_validate_json((d / "failure.json").read_text())
    manifest = RTLIntentManifest.model_validate_json((d / "manifest.json").read_text())
    # Artifact paths are rendered relative to the repo root so the golden is
    # byte-for-byte identical regardless of where the repo is checked out or
    # which directory the tests are run from.
    report = TriageEngine(trace, failure, manifest).run(
        repro_command="cx-triage demo",
        artifacts=[
            portable_path(d / "counter_fail.vcd", base=repo_dir),
            portable_path(d / "failure.json", base=repo_dir),
            portable_path(d / "manifest.json", base=repo_dir),
        ],
    )
    if narrate:
        report.llm_narrative = get_adapter("mock").narrate(report)
    return report


def test_golden_markdown(examples_dir, golden_dir, repo_dir):
    report = _build_report(examples_dir, repo_dir, narrate=True)
    got = render_markdown(report)
    expected = (golden_dir / "toy_counter_report.md").read_text()
    assert got == expected


def test_golden_json_structure(examples_dir, golden_dir, repo_dir):
    report = _build_report(examples_dir, repo_dir, narrate=False)
    got = json.loads(report.model_dump_json())
    expected = json.loads((golden_dir / "toy_counter_report.json").read_text())
    # Reproduction command differs between demo/triage invocations; compare the
    # substantive triage fields for stability.
    for key in (
        "property_name",
        "antecedent_cycle",
        "first_divergence_cycle",
        "rtl_cone",
        "hypotheses",
        "timeline",
        "citations",
    ):
        assert got[key] == expected[key], f"mismatch in {key}"


def test_mock_narrative_is_deterministic(examples_dir, repo_dir):
    r1 = _build_report(examples_dir, repo_dir, narrate=True)
    r2 = _build_report(examples_dir, repo_dir, narrate=True)
    assert r1.llm_narrative == r2.llm_narrative
    assert "advisory only" in r1.llm_narrative
