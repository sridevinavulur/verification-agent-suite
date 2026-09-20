"""Generate the bundled example reports (JSON + HTML).

Run:  python examples/generate_examples.py
Produces coverage_report.{json,html} and findings_report.{json,html} here.
"""
from __future__ import annotations

from pathlib import Path

from verification_report_kit import render_html, write_json
from verification_report_kit.examples_data import coverage_report, findings_report

HERE = Path(__file__).parent


def main() -> None:
    for name, builder in [
        ("coverage_report", coverage_report),
        ("findings_report", findings_report),
    ]:
        report = builder()
        write_json(report, HERE / f"{name}.json")
        (HERE / f"{name}.html").write_text(render_html(report), encoding="utf-8")
        print(f"wrote {name}.json + {name}.html")


if __name__ == "__main__":
    main()
