"""Regenerate golden + example output for the toy fixture repo.

Run from the repo root after an intentional parser change:

    python tests/regenerate_golden.py

This writes both:
  * ``tests/golden/toy_repo.json``      - stable golden (git_sha/hashes normalized)
  * ``examples/expected/toy_repo.{json,md}`` - the sample CLI output shown in docs

All outputs are portable (repo root recorded as ``.``, no absolute paths), so
they are byte-identical on any checkout. Review the diff before committing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import FIXTURE_REPO, GOLDEN_DIR, REPO_ROOT  # noqa: E402
from tb_recovery.recover import recover  # noqa: E402
from tb_recovery.report import render_markdown  # noqa: E402
from tb_recovery.serialize import report_to_json, report_to_json_stable  # noqa: E402

_EXAMPLE_COMMAND = "tb-recover inspect examples/toy_repo"


def main() -> None:
    report = recover(FIXTURE_REPO, command=_EXAMPLE_COMMAND)

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path = GOLDEN_DIR / "toy_repo.json"
    golden_path.write_text(report_to_json_stable(report), encoding="utf-8")
    print(f"wrote {golden_path}")

    expected_dir = REPO_ROOT / "examples" / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    (expected_dir / "toy_repo.json").write_text(
        report_to_json(report), encoding="utf-8"
    )
    (expected_dir / "toy_repo.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    print(f"wrote {expected_dir / 'toy_repo.json'}")
    print(f"wrote {expected_dir / 'toy_repo.md'}")


if __name__ == "__main__":
    main()
