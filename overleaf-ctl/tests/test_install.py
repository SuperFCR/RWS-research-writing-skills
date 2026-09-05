"""Installer boundaries; fresh dependency installation is also smoke-tested separately."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('overleaf_installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / 'source with spaces'
    for name in ['SKILL.md', 'tools/SKILL.md', 'writings/SKILL.md', 'tools/overleaf_sync/cli.py']:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('test source')
    (root / 'pyproject.toml').write_text('version = "0.3.1"\n')
    monkeypatch.setattr(installer, 'ROOT', root)
    return root


def test_check_on_fresh_checkout_is_read_only(source, capsys):
    before = sorted(str(p) for p in source.rglob('*'))
    assert installer.main(['--check']) == 1
    assert sorted(str(p) for p in source.rglob('*')) == before
    report = json.loads(capsys.readouterr().out)
    assert report['runtime_ready'] is False
    assert 'No usable .venv' in report['error']


def test_installer_does_not_replace_existing_cli(source, tmp_path, monkeypatch):
    monkeypatch.setattr(installer.shutil, 'which', lambda name: '/test/git')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    command = bin_dir / 'overleaf-ctl'
    command.write_text('another installation')
    assert installer.main(['--link-cli', '--bin-dir', str(bin_dir)]) == 1
    assert command.read_text() == 'another installation'
    assert not (source / '.venv').exists()


def test_broken_skill_link_is_not_replaced(source, tmp_path):
    target = tmp_path / 'skill'
    target.symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError, match='Refusing to replace'):
        installer.link_path(target, source, directory=True)
    assert target.is_symlink() and not target.exists()


def test_skill_link_is_idempotent_and_keeps_full_resource_tree(source, tmp_path):
    dest = tmp_path / 'skills/overleaf-ctl'
    installer.link_path(dest, source, directory=True)
    installer.link_path(dest, source, directory=True)
    assert dest.resolve() == source
    assert (dest / 'tools/overleaf_sync/cli.py').exists()
    assert (dest / 'writings/SKILL.md').exists()


def test_symlinked_venv_is_not_modified(source, tmp_path):
    env = tmp_path / 'shared-env'
    env.mkdir()
    (source / '.venv').symlink_to(env, target_is_directory=True)
    assert installer.main([]) == 1
    assert list(env.iterdir()) == []


def test_incomplete_venv_is_preserved(source, monkeypatch):
    monkeypatch.setattr(installer.shutil, 'which', lambda name: '/test/git')
    (source / '.venv').mkdir()
    marker = source / '.venv/keep'
    marker.write_text('keep')
    assert installer.main([]) == 1
    assert marker.read_text() == 'keep'


def test_install_failure_does_not_create_skill_or_command_links(source, tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(installer.shutil, 'which', lambda name: '/test/git')
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ['pip'])
    monkeypatch.setattr(installer.subprocess, 'run', fail)
    dest = tmp_path / 'skills/overleaf-ctl'
    bin_dir = tmp_path / 'bin'
    assert installer.main(['--skill-path', str(dest), '--link-cli', '--bin-dir', str(bin_dir)]) == 1
    assert not dest.exists() and not bin_dir.exists()


def test_python_install_path_uses_no_node_tex_or_global_pip(source, tmp_path, monkeypatch):
    monkeypatch.setattr(installer.shutil, 'which', lambda name: '/test/git' if name == 'git' else None)
    monkeypatch.setattr(installer, 'check_environment', lambda root: {'runtime_ready': True, 'version': '0.3.1'})
    commands = []
    def run(argv, **kwargs):
        commands.append(argv)
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(installer.subprocess, 'run', run)
    assert installer.main([]) == 0
    assert len(commands) == 2  # venv creation and installation into that venv
    assert commands[1][0] == str(installer.venv_python(source))
    assert commands[1][-1] == str(source)
    assert not any('node' in str(arg) or 'tlmgr' in str(arg) or '--upgrade' == arg for argv in commands for arg in argv)


def test_index_and_dev_are_opt_in(source, monkeypatch):
    monkeypatch.setattr(installer.shutil, 'which', lambda name: '/test/git')
    monkeypatch.setattr(installer, 'check_environment', lambda root: {'runtime_ready': True, 'version': '0.3.1'})
    commands = []
    monkeypatch.setattr(installer.subprocess, 'run', lambda argv, **kwargs: commands.append(argv))
    assert installer.main(['--dev', '--index-url', 'https://example.org/simple']) == 0
    assert str(source) + '[dev]' in commands[-1]
    assert commands[-1][-2:] == ['--index-url', 'https://example.org/simple']
