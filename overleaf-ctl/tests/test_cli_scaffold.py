from click.testing import CliRunner

from overleaf_sync.cli import main


def test_main_is_a_group_with_subcommands():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in [
        "login", "clone", "register", "list",
        "sync", "pull", "push", "status", "open", "compile",
    ]:
        assert cmd in result.output


def test_main_reports_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.3.1" in result.output


def test_all_subcommands_registered():
    from overleaf_sync.cli import main
    expected = {
        "login", "clone", "register", "list",
        "sync", "pull", "push", "status", "open", "compile",
    }
    assert expected.issubset(set(main.commands.keys()))
