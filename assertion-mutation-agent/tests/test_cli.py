import pathlib

from typer.testing import CliRunner

from assertion_mutation_agent.cli import app

runner = CliRunner()
ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def test_cli_mutate_lists_mutants():
    result = runner.invoke(app, ["mutate", str(EXAMPLES / "counter.v")])
    assert result.exit_code == 0
    assert "mutant(s) for module 'counter'" in result.stdout
    assert "relational_flip" in result.stdout


def test_cli_run_prints_score(tmp_path):
    json_out = tmp_path / "r.json"
    result = runner.invoke(
        app,
        [
            "run",
            str(EXAMPLES / "counter.v"),
            str(EXAMPLES / "counter.sva"),
            "--module",
            "counter",
            "--json-out",
            str(json_out),
        ],
    )
    assert result.exit_code == 0
    assert "Mutation score:" in result.stdout
    assert json_out.exists()


def test_cli_properties():
    result = runner.invoke(app, ["properties", str(EXAMPLES / "counter.sva")])
    assert result.exit_code == 0
    assert "p_reset_zero" in result.stdout


def test_cli_demo():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "Mutation Report" in result.stdout
    assert "Mutation score" in result.stdout


def test_cli_missing_file_errors():
    result = runner.invoke(app, ["mutate", "does_not_exist.v"])
    assert result.exit_code != 0
