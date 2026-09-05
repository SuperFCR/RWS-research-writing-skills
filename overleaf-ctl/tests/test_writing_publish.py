"""Publication boundaries exercised against real disposable Git remotes."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from overleaf_sync import gitops, publish, writing, compile as compile_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import Project
from tests.conftest import _git, _configure


def write(repo, name, text='local material'):
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def register(monkeypatch, repo):
    monkeypatch.setattr('overleaf_sync.cli.registry.get_project',
                        lambda alias: Project(alias=alias, path=str(repo), remote=str(repo)))


def test_writing_records_do_not_dirty_paper_and_preserve_resume(local_clone):
    original = (local_clone / 'main.tex').read_bytes()
    result = writing.initialize(local_clone)
    assert len(result['created']) == 4
    assert not gitops.get_status(local_clone).dirty
    progress = local_clone / '.writing/progress.md'
    progress.write_text('Accepted chapter 1; next: method')
    assert writing.initialize(local_clone)['created'] == []
    assert progress.read_text() == 'Accepted chapter 1; next: method'
    assert (local_clone / 'main.tex').read_bytes() == original
    assert not (local_clone / 'chapters').exists()
    assert not (local_clone / 'sections').exists()


def test_scaffold_is_opt_in_and_refuses_existing_sources_before_writes(local_clone):
    before = (local_clone / 'main.tex').read_bytes()
    with pytest.raises(ValueError, match='Existing TeX'):
        writing.initialize(local_clone, scaffold=True)
    assert not (local_clone / '.writing').exists()
    assert (local_clone / 'main.tex').read_bytes() == before


def test_empty_project_scaffold_has_resolving_inputs_and_no_parallel_tree(tmp_path):
    _git('init', str(tmp_path))
    result = writing.initialize(tmp_path, scaffold=True)
    assert result['layout']['main_candidates'] == ['main.tex']
    assert len(result['layout']['section_files']) == 8
    for value in result['layout']['inputs']['main.tex']:
        assert (tmp_path / (value + '.tex')).is_file()
    assert not (tmp_path / 'chapters').exists()
    assert not (tmp_path / 'latex-output').exists()
    assert not (tmp_path / 'plan').exists()
    ignored = _git('check-ignore', '.writing/progress.md', cwd=tmp_path)
    assert ignored.returncode == 0


def test_existing_sec_and_nested_main_are_recorded_without_renaming(local_clone):
    (local_clone / 'main.tex').unlink()
    write(local_clone, 'paper/main.tex', r'\documentclass{article}\begin{document}\input{sec/1_introduction}\end{document}')
    write(local_clone, 'paper/sec/1_introduction.tex', 'Original prose')
    result = writing.initialize(local_clone)
    assert result['layout']['section_files'] == ['paper/sec/1_introduction.tex']
    assert result['layout']['inputs']['paper/main.tex'] == ['sec/1_introduction']
    assert not (local_clone / 'sections').exists()


def test_symlink_state_is_rejected_without_touching_target(local_clone, tmp_path):
    target = tmp_path / 'elsewhere'
    target.mkdir()
    (local_clone / '.writing').symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        writing.initialize(local_clone)
    assert list(target.iterdir()) == []


def test_main_detection_skips_local_writing_sources(local_clone):
    (local_clone / 'main.tex').unlink()
    write(local_clone, '.writing/draft/main.tex', r'\documentclass{article}\begin{document}')
    write(local_clone, 'paper/main.tex', r'\documentclass{article}\begin{document}')
    assert compile_mod.detect_main(local_clone) == 'paper/main.tex'


def test_sync_sends_sources_but_not_writing_or_builds(local_clone, second_clone, monkeypatch):
    writing.initialize(local_clone)
    write(local_clone, '.writing/evidence-map.md')
    write(local_clone, '.outputs/main.pdf')
    write(local_clone, 'sections/1_intro.tex', 'Actual paper')
    write(local_clone, 'figures/result.pdf', 'Actual figure')
    write(local_clone, 'references.bib', '% bibliography')
    register(monkeypatch, local_clone)
    result = CliRunner().invoke(main, ['sync', 'paper'])
    assert result.exit_code == 0, result.output
    _git('pull', '--rebase', cwd=second_clone)
    assert (second_clone / 'sections/1_intro.tex').read_text() == 'Actual paper'
    assert (second_clone / 'figures/result.pdf').exists()
    assert (second_clone / 'references.bib').exists()
    assert not (second_clone / '.writing').exists()
    assert not (second_clone / '.outputs').exists()
    assert (local_clone / '.writing/evidence-map.md').exists()


@pytest.mark.parametrize('name', ['.writing/evidence.md', '.outputs/main.pdf', 'nested/.writing/private.md'])
def test_forced_staged_local_files_block_sync_before_commit(local_clone, bare_remote, monkeypatch, name):
    writing.initialize(local_clone)
    write(local_clone, name)
    _git('add', '-f', name, cwd=local_clone)
    before = _git('rev-parse', 'HEAD', cwd=local_clone).stdout
    register(monkeypatch, local_clone)
    result = CliRunner().invoke(main, ['sync', 'paper'])
    assert result.exit_code == 1, result.output
    assert name in result.output
    assert _git('rev-parse', 'HEAD', cwd=local_clone).stdout == before
    assert _git('rev-parse', 'main', cwd=bare_remote).stdout == before
    assert (local_clone / name).exists()


def test_deleted_local_file_still_blocks_outgoing_history(local_clone, bare_remote, monkeypatch):
    before = _git('rev-parse', 'HEAD', cwd=local_clone).stdout
    write(local_clone, '.writing/private.md')
    _git('add', '-f', '.writing/private.md', cwd=local_clone)
    _git('commit', '-m', 'accidental local material', cwd=local_clone)
    _git('rm', '.writing/private.md', cwd=local_clone)
    _git('commit', '-m', 'remove material from tip', cwd=local_clone)
    register(monkeypatch, local_clone)
    for command in ['check-push', 'push', 'sync']:
        result = CliRunner().invoke(main, [command, 'paper'])
        assert result.exit_code == 1, result.output
        assert 'Outgoing commit' in result.output
    assert _git('rev-parse', 'main', cwd=bare_remote).stdout == before


def test_custom_local_dir_ignored_but_real_figures_and_refs_visible(local_clone):
    writing.initialize(local_clone, local_only=['plan', 'latex_outputs'])
    write(local_clone, 'plan/progress.md')
    write(local_clone, 'latex_outputs/main.pdf')
    write(local_clone, 'refs/library.bib')
    write(local_clone, 'figures/plot.pdf')
    gitops.auto_commit(local_clone, 'paper dependencies')
    files = _git('ls-tree', '-r', '--name-only', 'HEAD', cwd=local_clone).stdout
    assert 'plan/' not in files and 'latex_outputs/' not in files
    assert 'refs/library.bib' in files and 'figures/plot.pdf' in files
    assert 'local-only.json' not in files


def test_force_added_custom_local_dir_is_blocked(local_clone):
    writing.initialize(local_clone, local_only=['draft records'])
    write(local_clone, 'draft records/evidence.md')
    _git('add', '-f', 'draft records/evidence.md', cwd=local_clone)
    with pytest.raises(gitops.GitError, match='draft records/evidence.md'):
        publish.assert_index_safe(local_clone)


@pytest.mark.parametrize('path', ['../plan', '/', '.git', 'a/../plan', '*.pdf', 'a\nb'])
def test_local_config_rejects_escaping_or_nonliteral_paths(local_clone, path):
    with pytest.raises(ValueError):
        writing.initialize(local_clone, local_only=[path])
    assert not (local_clone / '.writing').exists()


def test_corrupt_local_config_fails_closed(local_clone):
    cfg = publish.git_path(local_clone, 'info/overleaf-ctl-local-only.json')
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text('{bad')
    with pytest.raises(gitops.GitError, match='Invalid local-only'):
        publish.assert_publish_safe(local_clone)


def test_worktree_excludes_and_private_state(local_clone, tmp_path):
    wt = tmp_path / 'worktree'
    _git('worktree', 'add', '-b', 'worktree-test', str(wt), cwd=local_clone)
    writing.initialize(wt)
    assert (wt / '.git').is_file()
    assert not gitops.get_status(wt).dirty
    assert _git('check-ignore', '.writing/progress.md', cwd=wt).returncode == 0
    assert not gitops.rebase_in_progress(wt)


def test_exclude_append_handles_missing_final_newline(local_clone):
    exclude = publish.git_path(local_clone, 'info/exclude')
    exclude.write_text('keep-this-rule')
    gitops.ensure_local_excludes(local_clone, ['.writing/'])
    assert exclude.read_text() == 'keep-this-rule\n.writing/\n'


def test_missing_upstream_blocks_push_without_guess(local_clone):
    _git('branch', '--unset-upstream', cwd=local_clone)
    with pytest.raises(gitops.GitError, match='tracking origin'):
        gitops.push(local_clone)


def test_previously_published_private_file_can_be_untracked_without_deleting_local(local_clone):
    write(local_clone, '.writing/old.md')
    _git('add', '-f', '.writing/old.md', cwd=local_clone)
    _git('commit', '-m', 'legacy accidental publication', cwd=local_clone)
    _git('push', cwd=local_clone)  # simulate an old client before the guard existed
    _git('rm', '--cached', '.writing/old.md', cwd=local_clone)
    _git('commit', '-m', 'explicit cleanup by user', cwd=local_clone)
    gitops.push(local_clone)
    assert (local_clone / '.writing/old.md').exists()


def test_gitignore_negation_cannot_expose_local_files_to_auto_commit(local_clone):
    writing.initialize(local_clone)
    write(local_clone, '.gitignore', '!.writing/\n')
    before = _git('rev-parse', 'HEAD', cwd=local_clone).stdout
    with pytest.raises(gitops.GitError, match='Local-only'):
        gitops.auto_commit(local_clone, 'must not stage private records')
    assert _git('rev-parse', 'HEAD', cwd=local_clone).stdout == before
    assert _git('diff', '--cached', '--name-only', cwd=local_clone).stdout == ''


def test_actual_push_refreshes_stale_upstream_history(local_clone, bare_remote):
    original = _git('rev-parse', 'HEAD', cwd=local_clone).stdout.strip()
    write(local_clone, '.writing/private.md')
    _git('add', '-f', '.writing/private.md', cwd=local_clone)
    _git('commit', '-m', 'old client private record', cwd=local_clone)
    _git('rm', '.writing/private.md', cwd=local_clone)
    _git('commit', '-m', 'tip clean', cwd=local_clone)
    _git('push', cwd=local_clone)
    _git('update-ref', 'refs/heads/main', original, cwd=bare_remote)
    publish.assert_publish_safe(local_clone)
    with pytest.raises(gitops.GitError, match='Outgoing commit'):
        gitops.push(local_clone)
    assert _git('rev-parse', 'main', cwd=bare_remote).stdout.strip() == original


def test_push_url_mismatch_is_rejected_before_contacting_destination(local_clone):
    _git('remote', 'set-url', '--push', 'origin', '/nonexistent/other.git', cwd=local_clone)
    with pytest.raises(gitops.GitError, match='single origin push URL'):
        gitops.push(local_clone)


def test_explicit_branch_push_does_not_send_configured_extra_refs(local_clone, bare_remote):
    write(local_clone, 'section.tex', 'public prose')
    gitops.auto_commit(local_clone, 'manuscript update')
    _git('tag', '-a', 'local-review', '-m', 'local review metadata', cwd=local_clone)
    _git('config', 'push.followTags', 'true', cwd=local_clone)
    _git('config', 'remote.origin.push', 'refs/tags/*:refs/tags/*', cwd=local_clone)
    gitops.push(local_clone)
    assert _git('tag', '--list', cwd=bare_remote).stdout == ''
    assert 'section.tex' in _git('ls-tree', '-r', '--name-only', 'main', cwd=bare_remote).stdout


@pytest.mark.parametrize('template', ['venue.cls', 'assets/custom.sty', 'bib/format.bst'])
def test_scaffold_refuses_template_only_project(tmp_path, template):
    _git('init', str(tmp_path))
    write(tmp_path, template, 'Existing venue template')
    with pytest.raises(ValueError, match='Existing TeX'):
        writing.initialize(tmp_path, scaffold=True)
    assert not (tmp_path / 'main.tex').exists()
    assert not (tmp_path / '.writing').exists()
    assert (tmp_path / template).read_text() == 'Existing venue template'


def test_local_path_init_needs_no_overleaf_account_or_registry(tmp_path, monkeypatch):
    _git('init', str(tmp_path))
    def no_registry(*args):
        raise AssertionError('Local path initialization must not access the registry')
    monkeypatch.setattr('overleaf_sync.cli.registry.get_project', no_registry)
    result = CliRunner().invoke(main, ['writing', 'init', '--path', str(tmp_path), '--scaffold'])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'sections/1_intro.tex').is_file()
    assert _git('remote', cwd=tmp_path).stdout == ''


def test_init_rejects_alias_and_path_together_before_changes(tmp_path):
    result = CliRunner().invoke(main, ['writing', 'init', 'paper', '--path', str(tmp_path)])
    assert result.exit_code == 2
    assert list(tmp_path.iterdir()) == []
