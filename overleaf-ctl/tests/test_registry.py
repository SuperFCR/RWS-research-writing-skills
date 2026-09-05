# tests/test_registry.py
from pathlib import Path

from overleaf_sync.registry import (
    Project,
    load_registry,
)


def test_project_dataclass_fields_and_defaults():
    p = Project(alias="paper", path="/tmp/paper", remote="https://git.overleaf.com/abc")
    assert p.alias == "paper"
    assert p.path == "/tmp/paper"
    assert p.remote == "https://git.overleaf.com/abc"
    assert p.main is None
    assert p.engine is None
    p2 = Project(alias="b", path="/p", remote="r", main="main.tex", engine="pdflatex")
    assert p2.main == "main.tex"
    assert p2.engine == "pdflatex"


def test_load_registry_missing_file_returns_empty(tmp_path: Path):
    missing = tmp_path / "does-not-exist" / "projects.json"
    assert load_registry(missing) == {}


def test_load_registry_empty_dict_when_file_absent_default_factory(tmp_path: Path):
    result = load_registry(tmp_path / "projects.json")
    assert isinstance(result, dict)
    assert result == {}


import json
import stat

from overleaf_sync.registry import save_registry


def test_save_then_load_round_trip(tmp_path: Path):
    reg_path = tmp_path / "cfg" / "overleaf-sync" / "projects.json"
    projects = {
        "paper": Project(
            alias="paper",
            path="/Users/x/overleaf/paper",
            remote="https://git.overleaf.com/AAA",
            main="main.tex",
            engine="pdflatex",
        ),
        "thesis": Project(
            alias="thesis",
            path="/Users/x/overleaf/thesis",
            remote="https://git.overleaf.com/BBB",
        ),
    }
    save_registry(projects, reg_path)
    loaded = load_registry(reg_path)
    assert loaded == projects
    assert loaded["thesis"].main is None
    assert loaded["thesis"].engine is None


def test_save_registry_persists_version_and_alias_not_duplicated_in_fields(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    save_registry({"a": Project(alias="a", path="/p", remote="r")}, reg_path)
    raw = json.loads(reg_path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert "a" in raw["projects"]
    # alias is the JSON key, not stored redundantly inside the object
    assert "alias" not in raw["projects"]["a"]
    assert raw["projects"]["a"]["path"] == "/p"


def test_save_registry_file_and_dir_permissions(tmp_path: Path):
    reg_path = tmp_path / "secret" / "projects.json"
    save_registry({"a": Project(alias="a", path="/p", remote="r")}, reg_path)
    dir_mode = stat.S_IMODE(reg_path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(reg_path.stat().st_mode)
    assert dir_mode == 0o700
    assert file_mode == 0o600


def test_save_registry_is_atomic_no_temp_leftover(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    save_registry({"a": Project(alias="a", path="/p", remote="r")}, reg_path)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "projects.json"]
    assert leftovers == []


import pytest

from overleaf_sync.registry import AliasExistsError, add_project


def test_add_project_writes_to_registry(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="paper", path="/p", remote="r"), reg_path)
    loaded = load_registry(reg_path)
    assert "paper" in loaded
    assert loaded["paper"].path == "/p"


def test_add_project_appends_without_clobbering(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="b", path="/b", remote="rb"), reg_path)
    loaded = load_registry(reg_path)
    assert set(loaded) == {"a", "b"}


def test_add_project_duplicate_alias_raises(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="paper", path="/p1", remote="r1"), reg_path)
    with pytest.raises(AliasExistsError):
        add_project(Project(alias="paper", path="/p2", remote="r2"), reg_path)
    # original is untouched
    assert load_registry(reg_path)["paper"].path == "/p1"


from overleaf_sync.registry import UnknownAliasError, get_project


def test_get_project_returns_project(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="paper", path="/p", remote="r", main="m.tex"), reg_path)
    got = get_project("paper", reg_path)
    assert got == Project(alias="paper", path="/p", remote="r", main="m.tex")


def test_get_project_unknown_raises_and_lists_known(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="alpha", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="beta", path="/b", remote="rb"), reg_path)
    with pytest.raises(UnknownAliasError) as excinfo:
        get_project("gamma", reg_path)
    msg = str(excinfo.value)
    assert "gamma" in msg
    assert "alpha" in msg
    assert "beta" in msg


def test_get_project_unknown_empty_registry(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    with pytest.raises(UnknownAliasError):
        get_project("nope", reg_path)


from overleaf_sync.registry import list_projects, remove_project


def test_list_projects_empty(tmp_path: Path):
    assert list_projects(tmp_path / "projects.json") == []


def test_list_projects_returns_all(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="b", path="/b", remote="rb"), reg_path)
    result = list_projects(reg_path)
    assert isinstance(result, list)
    assert {p.alias for p in result} == {"a", "b"}
    assert all(isinstance(p, Project) for p in result)


def test_remove_project_deletes_alias(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="b", path="/b", remote="rb"), reg_path)
    remove_project("a", reg_path)
    loaded = load_registry(reg_path)
    assert set(loaded) == {"b"}


def test_remove_project_unknown_raises_and_lists_known(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    with pytest.raises(UnknownAliasError) as excinfo:
        remove_project("zzz", reg_path)
    assert "zzz" in str(excinfo.value)
    assert "a" in str(excinfo.value)
    # registry unchanged
    assert set(load_registry(reg_path)) == {"a"}
