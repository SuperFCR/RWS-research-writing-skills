# overleaf_sync/registry.py
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

# INTENTIONAL legacy path: the tool was renamed overleaf-sync -> overleaf-ctl,
# but existing users' registries live here. Do NOT "tidy up" this name to
# overleaf-ctl without a migrate-on-load (old path exists + new path absent ->
# move), or every registered project silently disappears.
REGISTRY_PATH: Path = Path.home() / ".config" / "overleaf-sync" / "projects.json"


class UnknownAliasError(KeyError):
    """Raised when an alias is not present in the registry."""


class AliasExistsError(ValueError):
    """Raised when adding a project whose alias already exists."""


@dataclass
class Project:
    alias: str
    path: str
    remote: str
    main: str | None = None
    engine: str | None = None


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Project]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    projects: dict[str, Project] = {}
    for alias, fields in raw.get("projects", {}).items():
        projects[alias] = Project(
            alias=alias,
            path=fields["path"],
            remote=fields["remote"],
            main=fields.get("main"),
            engine=fields.get("engine"),
        )
    return projects


def _to_payload(projects: dict[str, Project]) -> dict:
    out: dict[str, dict] = {}
    for alias, project in projects.items():
        fields = asdict(project)
        fields.pop("alias", None)
        out[alias] = {k: v for k, v in fields.items() if v is not None}
    return {"version": 1, "projects": out}


def save_registry(projects: dict[str, Project], path: Path = REGISTRY_PATH) -> None:
    path = Path(path)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    payload = _to_payload(projects)
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=".projects.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def add_project(project: Project, path: Path = REGISTRY_PATH) -> None:
    projects = load_registry(path)
    if project.alias in projects:
        raise AliasExistsError(
            f"alias {project.alias!r} already registered; "
            f"known aliases: {sorted(projects)}"
        )
    projects[project.alias] = project
    save_registry(projects, path)


def get_project(alias: str, path: Path = REGISTRY_PATH) -> Project:
    projects = load_registry(path)
    if alias not in projects:
        raise UnknownAliasError(
            f"unknown alias {alias!r}; known aliases: {sorted(projects)}"
        )
    return projects[alias]


def list_projects(path: Path = REGISTRY_PATH) -> list[Project]:
    return list(load_registry(path).values())


def remove_project(alias: str, path: Path = REGISTRY_PATH) -> None:
    projects = load_registry(path)
    if alias not in projects:
        raise UnknownAliasError(
            f"unknown alias {alias!r}; known aliases: {sorted(projects)}"
        )
    del projects[alias]
    save_registry(projects, path)
