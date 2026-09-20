"""Regenerate golden triage reports from the bundled example manifests.

Run after an *intended* change to the analysis output::

    python tests/regenerate_golden.py

then review the diff before committing.
"""

from __future__ import annotations

from pathlib import Path

from cdc_rdc_triage import __version__
from cdc_rdc_triage.analyze import analyze_manifest
from cdc_rdc_triage.report import render_markdown
from cdc_rdc_triage.serialize import load_manifest, report_to_json

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples" / "expected"
GOLDEN = REPO / "tests" / "golden"

CASES = ["cdc_sync", "rdc_example", "single_clock"]


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        manifest = load_manifest(EXAMPLES / f"{name}.manifest.json")
        report = analyze_manifest(manifest, tool_version=__version__)
        text = report_to_json(report)
        (GOLDEN / f"{name}.report.json").write_text(text, encoding="utf-8")
        (EXAMPLES / f"{name}.report.json").write_text(text, encoding="utf-8")
        (EXAMPLES / f"{name}.report.md").write_text(
            render_markdown(report), encoding="utf-8"
        )
        print(f"regenerated {name}")


if __name__ == "__main__":
    main()
