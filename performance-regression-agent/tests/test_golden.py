"""Golden-output tests: the committed report must match a fresh run."""

from __future__ import annotations

import json
from pathlib import Path

from perf_regression_agent.benchmark import build_dataset
from perf_regression_agent.detector import analyze
from perf_regression_agent.io_utils import load_dataset, report_to_json
from perf_regression_agent.renderer import render_markdown

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_JSON = ROOT / "reports" / "golden_report.json"
GOLDEN_MD = ROOT / "reports" / "golden_report.md"
BENCHMARK = ROOT / "examples" / "telemetry" / "benchmark.json"


def test_committed_benchmark_matches_generator():
    on_disk = load_dataset(BENCHMARK)
    fresh = build_dataset()
    assert on_disk.model_dump() == fresh.model_dump()


def test_golden_json_matches_current_output():
    report = analyze(build_dataset())
    current = json.loads(report_to_json(report))
    golden = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
    assert current == golden, (
        "Golden JSON drifted. Regenerate with: perf-regress demo "
        "--json reports/golden_report.json --md reports/golden_report.md"
    )


def test_golden_markdown_matches_current_output():
    report = analyze(build_dataset())
    current = render_markdown(report)
    golden = GOLDEN_MD.read_text(encoding="utf-8")
    assert current == golden


def test_golden_reports_the_two_injected_regressions():
    golden = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
    assert golden["n_regressions"] == 2
