from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import UnknownAliasError


def test_status_unknown_alias_lists_known(monkeypatch):
    def boom(alias):
        raise UnknownAliasError("未知别名 'nope'；已登记: paperA, paperB")
    monkeypatch.setattr(cli_mod.registry, "get_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["status", "nope"])

    assert result.exit_code != 0
    assert "paperA" in result.output
    assert "paperB" in result.output


def test_sync_unknown_alias_lists_known(monkeypatch):
    def boom(alias):
        raise UnknownAliasError("未知别名 'x'；已登记: paperA")
    monkeypatch.setattr(cli_mod.registry, "get_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "x"])

    assert result.exit_code != 0
    assert "paperA" in result.output
