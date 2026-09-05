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
    assert data["project"]["version"] == "0.3.1"
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


def test_npm_package_excludes_caches_and_includes_installer(tmp_path):
    import json
    import shutil
    import subprocess
    import pytest
    npm = shutil.which('npm')
    if not npm:
        pytest.skip('npm is optional for the Python installation')
    source = tmp_path / 'source'
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('.venv', '__pycache__', '*.egg-info', '.pytest_cache', 'node_modules'))
    cache = source / 'scripts/__pycache__/install.cpython-310.pyc'
    cache.parent.mkdir()
    cache.write_bytes(b'generated cache')
    result = subprocess.run([npm, 'pack', '--dry-run', '--json'], cwd=source, capture_output=True, text=True, check=True)
    paths = {item['path'] for item in json.loads(result.stdout)[0]['files']}
    assert 'scripts/install.py' in paths and 'writings/SKILL.md' in paths
    assert not any('__pycache__' in p or '.venv/' in p or p.endswith('.pyc') for p in paths)
