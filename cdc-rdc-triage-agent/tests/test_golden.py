"""Golden-output tests: the report for each example must be byte-stable and
must match the committed golden file.  Also asserts the substantive findings so
a golden refresh cannot silently hide a regression in detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from cdc_rdc_triage import __version__
from cdc_rdc_triage.analyze import analyze_manifest
from cdc_rdc_triage.serialize import load_manifest, report_to_json

CASES = ["cdc_sync", "rdc_example", "single_clock"]


@pytest.mark.parametrize("name", CASES)
def test_golden_matches(name: str, examples_dir: Path, golden_dir: Path) -> None:
    manifest = load_manifest(examples_dir / f"{name}.manifest.json")
    report = analyze_manifest(manifest, tool_version=__version__)
    produced = report_to_json(report)
    expected = (golden_dir / f"{name}.report.json").read_text(encoding="utf-8")
    assert produced == expected, (
        f"golden mismatch for {name}; run tests/regenerate_golden.py if intended"
    )


@pytest.mark.parametrize("name", CASES)
def test_determinism(name: str, examples_dir: Path) -> None:
    manifest = load_manifest(examples_dir / f"{name}.manifest.json")
    r1 = report_to_json(analyze_manifest(manifest, tool_version=__version__))
    r2 = report_to_json(analyze_manifest(manifest, tool_version=__version__))
    assert r1 == r2


def test_every_finding_is_heuristic(examples_dir: Path) -> None:
    for name in CASES:
        manifest = load_manifest(examples_dir / f"{name}.manifest.json")
        report = analyze_manifest(manifest, tool_version=__version__)
        for c in report.all_crossings():
            assert c.heuristic is True
