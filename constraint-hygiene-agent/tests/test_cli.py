from typer.testing import CliRunner

from constraint_hygiene.cli import app

runner = CliRunner()


def test_cli_review_md(good_sva, manifest_path):
    result = runner.invoke(
        app, ["review", str(good_sva), "--manifest", str(manifest_path)]
    )
    assert result.exit_code == 0
    assert "Constraint Hygiene Report" in result.stdout
    assert "Signal ownership classification" in result.stdout


def test_cli_review_json(bad_sva, manifest_path):
    result = runner.invoke(
        app, ["review", str(bad_sva), "-m", str(manifest_path), "-f", "json"]
    )
    assert result.exit_code == 0
    assert '"contradiction_candidates"' in result.stdout


def test_cli_fail_on_error_exit_code(bad_sva, manifest_path):
    result = runner.invoke(
        app,
        ["review", str(bad_sva), "-m", str(manifest_path), "-f", "json", "--fail-on", "error"],
    )
    assert result.exit_code == 1  # bad corpus has error-severity findings


def test_cli_fail_on_error_clean_passes(good_sva, manifest_path):
    result = runner.invoke(
        app,
        ["review", str(good_sva), "-m", str(manifest_path), "-f", "json", "--fail-on", "error"],
    )
    assert result.exit_code == 0  # good corpus has no error-severity findings


def test_cli_schema():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    assert '"HygieneReport"' in result.stdout or '"title"' in result.stdout
