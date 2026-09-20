"""Golden-report tests. Compare the analysis portion of the report against
checked-in expected outputs, ignoring volatile provenance fields."""

import json

from constraint_hygiene.engine import analyze_files
from constraint_hygiene.report import render_markdown

_VOLATILE = {"provenance"}


def _stable(report_dict: dict) -> dict:
    return {k: v for k, v in report_dict.items() if k not in _VOLATILE}


def test_good_golden_json(examples_dir, good_sva, manifest_path):
    report = analyze_files(good_sva, manifest_path)
    got = _stable(json.loads(report.model_dump_json()))
    expected = _stable(json.loads((examples_dir / "expected" / "good.json").read_text()))
    assert got == expected


def test_bad_golden_json(examples_dir, bad_sva, manifest_path):
    report = analyze_files(bad_sva, manifest_path)
    got = _stable(json.loads(report.model_dump_json()))
    expected = _stable(json.loads((examples_dir / "expected" / "bad.json").read_text()))
    assert got == expected


def test_bad_golden_markdown(examples_dir, bad_sva, manifest_path):
    # Markdown is generated from provenance-bearing report; strip the Inputs line
    # which carries absolute-vs-relative path differences deterministically here
    # (analyze_files stores the passed path). Compare full text otherwise.
    report = analyze_files(bad_sva, manifest_path, command="")
    got = render_markdown(report)
    expected = (examples_dir / "expected" / "bad.md").read_text()
    # Normalize the Inputs line (paths differ by invocation) before comparing.
    got_n = _norm_inputs(got)
    exp_n = _norm_inputs(expected)
    assert got_n == exp_n


def _norm_inputs(md: str) -> str:
    return "\n".join(
        "- Inputs: <normalized>" if line.startswith("- Inputs:") else line
        for line in md.splitlines()
    )
