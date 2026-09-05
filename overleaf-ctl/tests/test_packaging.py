# tests/test_packaging.py
from pathlib import Path

try:
    import tomllib  # Python >=3.11
except ModuleNotFoundError:  # 3.10 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent


def _load_pyproject():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def test_project_name_and_version():
    data = _load_pyproject()
    assert data["project"]["name"] == "overleaf-ctl"
    assert data["project"]["version"] == "0.3.0"
    assert data["project"]["requires-python"] == ">=3.10"


def test_runtime_dependencies_declared():
    deps = " ".join(_load_pyproject()["project"]["dependencies"])
    # click>=8.2 is required so CliRunner merges stderr into result.output.
    assert "click>=8.2" in deps
    assert "rich>=13" in deps


def test_console_script_entrypoint():
    scripts = _load_pyproject()["project"]["scripts"]
    assert scripts["overleaf-ctl"] == "overleaf_sync.cli:main"
    assert scripts["overleaf"] == "overleaf_sync.cli:main"


def test_setuptools_build_backend():
    assert _load_pyproject()["build-system"]["build-backend"] == "setuptools.build_meta"


def test_dev_extra_has_pytest():
    extras = _load_pyproject()["project"]["optional-dependencies"]["dev"]
    assert any(e.startswith("pytest") for e in extras)


def test_requirements_txt_lists_deps():
    text = (ROOT / "requirements.txt").read_text()
    assert "click>=8.2" in text
    assert "rich>=13" in text
