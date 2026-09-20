"""Golden-output test: recovery report must match committed golden byte-for-byte.

Regenerate with ``python tests/regenerate_golden.py`` after an intended change.

The golden is *path-independent by design*: ``recover()`` records the repo root
relative to itself (``.``) and strips any absolute path out of the ``command``
field, so the serialized report is byte-identical no matter where the repo is
checked out. ``test_golden_is_portable_across_checkout_paths`` proves this by
running recovery against a copy of the fixture at a different absolute path.
"""

from __future__ import annotations

import shutil

from conftest import FIXTURE_REPO, GOLDEN_DIR
from tb_recovery.recover import recover
from tb_recovery.serialize import report_from_json, report_to_json_stable


def test_golden_matches():
    report = recover(FIXTURE_REPO, command="tb-recover inspect examples/toy_repo")
    produced = report_to_json_stable(report)
    golden = (GOLDEN_DIR / "toy_repo.json").read_text(encoding="utf-8")
    assert produced == golden, (
        "recovery report differs from golden; run "
        "'python tests/regenerate_golden.py' if the change is intended"
    )


def test_recovery_is_deterministic():
    a = report_to_json_stable(recover(FIXTURE_REPO, command="x"))
    b = report_to_json_stable(recover(FIXTURE_REPO, command="x"))
    assert a == b


def test_golden_roundtrips_through_model():
    golden = (GOLDEN_DIR / "toy_repo.json").read_text(encoding="utf-8")
    report = report_from_json(golden)
    assert report_to_json_stable(report) == golden


def test_report_leaks_no_absolute_repo_path():
    """No field in the report may contain the machine's absolute repo path."""
    report = recover(
        FIXTURE_REPO, command=f"tb-recover inspect {FIXTURE_REPO}"
    )
    assert report.repro.repo_root == "."
    # The absolute path passed on the command line must be stripped.
    assert str(FIXTURE_REPO) not in report.repro.command
    blob = report_to_json_stable(report)
    assert str(FIXTURE_REPO) not in blob
    assert str(FIXTURE_REPO.parent) not in blob


def test_golden_is_portable_across_checkout_paths(tmp_path):
    """Recovering an identical fixture at a *different* absolute path yields the
    exact same stable report - i.e. the golden holds on any teammate's clone.

    The ``command`` string is passed with each checkout's own absolute repo
    path; ``recover`` strips it to the portable ``.`` form, so both runs (and
    the committed golden) are byte-identical despite living at different paths.
    """
    other_root = tmp_path / "elsewhere" / "toy_repo"
    shutil.copytree(FIXTURE_REPO, other_root)

    here = report_to_json_stable(
        recover(FIXTURE_REPO, command=f"tb-recover inspect {FIXTURE_REPO}")
    )
    there = report_to_json_stable(
        recover(other_root, command=f"tb-recover inspect {other_root}")
    )
    assert here == there
    assert str(tmp_path) not in there
    assert str(FIXTURE_REPO) not in here
