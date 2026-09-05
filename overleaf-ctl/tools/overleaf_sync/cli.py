from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from . import auth, compile as compile_mod, gitops, registry, tex, writing, publish
from .registry import Project

console = Console()
err_console = Console(stderr=True)


def _mask_token(token: str) -> str:
    """Show enough of a token to identify it, never the secret itself."""
    if len(token) <= 8:
        return token[:2] + "…"
    return f"{token[:4]}…{token[-4:]}"


def _open_path(path: str) -> None:
    """Open a file/dir with the platform's default opener."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: attr only exists on Windows
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


@click.group()
@click.version_option(__version__, prog_name="overleaf-ctl")
def main() -> None:
    """Overleaf 本地同步 CLI：本地 VSCode 编辑 + git 双向同步 + 本地编译。"""


def _handle_registry_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except gitops.GitError as exc:
            err_console.print(str(exc), style="red", markup=False)
            raise SystemExit(1)
        except (registry.UnknownAliasError, registry.AliasExistsError) as exc:
            # UnknownAliasError subclasses KeyError, whose str() wraps the message
            # in repr quotes; print the raw message instead.
            msg = exc.args[0] if exc.args else str(exc)
            err_console.print(f"[red]{msg}[/red]")
            raise SystemExit(2)
    return wrapper


@main.command()
@click.option("--host", default=auth.DEFAULT_HOST, show_default=True,
              help="Overleaf git 主机名。")
@click.option("--token-stdin", "token_stdin", is_flag=True,
              help="从 stdin 读取 token（适合管道）。")
def login(host: str, token_stdin: bool) -> None:
    """读取 Overleaf git token 并存入系统凭据库（绝不落盘）。"""
    auth.ensure_credential_helper()
    existing = auth.get_credential(host=host)
    # --token-stdin 是非交互管道场景，stdin 留给 token 本身，跳过确认直接覆盖。
    if existing and not token_stdin:
        console.print(
            f"[yellow]{host} 已有凭据：username=git，"
            f"token={_mask_token(existing)}[/yellow]")
        if not click.confirm("覆盖为新 token？", default=False):
            console.print("已保留现有凭据（如需删除请用 overleaf-ctl logout）。")
            return
    if token_stdin:
        token = click.get_text_stream("stdin").readline().strip()
    else:
        token = getpass("Overleaf git token: ").strip()
    if not token:
        err_console.print("[red]token 为空，已取消。[/red]")
        raise SystemExit(1)
    auth.store_token(token, host=host)
    console.print(f"[green]已为 {host} 存入凭据（系统凭据库）。[/green]")


@main.command()
@click.option("--host", default=auth.DEFAULT_HOST, show_default=True,
              help="Overleaf git 主机名。")
@click.option("--yes", is_flag=True, help="跳过确认直接删除。")
def logout(host: str, yes: bool) -> None:
    """从系统凭据库删除已存的 Overleaf git token。"""
    existing = auth.get_credential(host=host)
    if not existing:
        console.print(f"[yellow]{host} 当前没有已存的凭据。[/yellow]")
        return
    console.print(f"{host} 当前凭据：username=git，token={_mask_token(existing)}")
    if not yes and not click.confirm("确认删除？", default=False):
        console.print("已取消。")
        return
    auth.erase_credential(host=host)
    console.print(f"[green]已删除 {host} 的凭据。[/green]")


@main.command()
@click.argument("url")
@click.argument("alias")
@click.option("--path", "dest", type=click.Path(file_okay=False),
              default=None, help="克隆目标目录，默认 ~/overleaf/<别名>。")
@_handle_registry_errors
def clone(url: str, alias: str, dest: str | None) -> None:
    """克隆 Overleaf 项目到本地并登记到 registry。"""
    target = (Path(dest).expanduser() if dest else Path.home() / "overleaf" / alias).resolve()
    try:
        gitops.clone(url, target)
    except gitops.GitError as exc:
        err_console.print(f"[red]克隆失败：{exc}[/red]")
        err_console.print("[yellow]认证失败？先运行 `overleaf-ctl login`。[/yellow]")
        raise SystemExit(1)
    # registry write happens only after a successful clone (no half-register)
    registry.add_project(Project(alias=alias, path=str(target), remote=url))
    gitops.ensure_local_excludes(target, gitops.TEX_LOCAL_EXCLUDES)
    console.print(f"[green]已克隆 {alias} -> {target}[/green]")


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.argument("alias")
@_handle_registry_errors
def register(path: str, alias: str) -> None:
    """把已有的本地 Overleaf git 仓库登记到 registry。"""
    path = str(Path(path).expanduser().resolve())
    if not gitops.is_git_repo(path):
        err_console.print(f"[red]{path} 不是 git 仓库，无法登记。[/red]")
        raise SystemExit(1)
    remote = gitops.get_remote_url(path)
    if not remote or "overleaf.com" not in remote:
        err_console.print(
            f"[red]remote 不是 Overleaf（{remote or '无 remote'}），拒绝登记。[/red]")
        raise SystemExit(1)
    registry.add_project(Project(alias=alias, path=str(path), remote=remote))
    gitops.ensure_local_excludes(path, gitops.TEX_LOCAL_EXCLUDES)
    console.print(f"[green]已登记 {alias} -> {path}[/green]")


@main.command(name="list")
def list_cmd() -> None:
    """列出所有已登记项目及其状态。"""
    projects = registry.list_projects()
    if not projects:
        console.print("[yellow]registry 无项目（empty），先 overleaf-ctl clone/register。[/yellow]")
        return
    table = Table(title="overleaf-ctl projects")
    table.add_column("别名", style="cyan")
    table.add_column("路径")
    table.add_column("远端")
    table.add_column("状态")
    for proj in projects:
        try:
            st = gitops.get_status(proj.path)
            state = "dirty" if st.dirty else "clean"
            if st.ahead:
                state += f" ↑{st.ahead}"
            if st.behind:
                state += f" ↓{st.behind}"
        except Exception:
            state = "?"
        table.add_row(proj.alias, proj.path, proj.remote, state)
    console.print(table)


@main.command()
@click.argument("alias")
@click.option("--no-commit", "no_commit", is_flag=True,
              help="不自动提交（脏工作区时拒绝执行）。")
@click.option("--message", "message", default=None, help="自定义提交信息。")
@_handle_registry_errors
def sync(alias: str, no_commit: bool, message: str | None) -> None:
    """核心：auto-commit → pull --rebase → push；冲突永远停下让用户解决。"""
    proj = registry.get_project(alias)
    repo = proj.path
    # Build artifacts / .DS_Store must never be auto-committed to Overleaf.
    gitops.ensure_local_excludes(repo, gitops.TEX_LOCAL_EXCLUDES)

    # Step 1: unfinished rebase -> continue mode
    if gitops.rebase_in_progress(repo):
        unmerged = gitops.unmerged_files(repo)
        if unmerged:
            err_console.print("[red]仍有未解决冲突：[/red]")
            for f in unmerged:
                err_console.print(f"  - {f}")
            err_console.print(
                f"[yellow]在 VSCode 解决后重跑 overleaf-ctl sync {alias}[/yellow]")
            raise SystemExit(1)
        cont = gitops.rebase_continue(repo)
        if cont.conflict:
            err_console.print("[red]仍有未解决冲突：[/red]")
            for f in gitops.unmerged_files(repo):
                err_console.print(f"  - {f}")
            err_console.print(
                f"[yellow]在 VSCode 解决后重跑 overleaf-ctl sync {alias}[/yellow]")
            raise SystemExit(1)
        _finish_push(repo)
        return

    # Step 2: commit
    status = gitops.get_status(repo)
    if status.dirty:
        if no_commit:
            err_console.print("[red]工作区有改动，--no-commit 模式下请先 git commit/stash。[/red]")
            raise SystemExit(1)
        msg = message or f"overleaf-ctl: {datetime.now().astimezone().isoformat()}"
        gitops.auto_commit(repo, msg)

    # Step 3: pull --rebase
    r = gitops.pull_rebase(repo)
    if r.conflict:
        err_console.print("[red]pull --rebase 冲突，已保留现场（未 abort）：[/red]")
        for f in gitops.unmerged_files(repo):
            err_console.print(f"  - {f}")
        err_console.print(
            f"[yellow]在 VSCode 解决后重跑 overleaf-ctl sync {alias}[/yellow]")
        raise SystemExit(1)

    # Step 4: push
    _finish_push(repo)


def _finish_push(repo: str) -> None:
    summary = gitops.push(repo)
    console.print(f"[green]同步完成：{summary}[/green]")


@main.command()
@click.argument("alias")
@_handle_registry_errors
def pull(alias: str) -> None:
    """git pull --rebase（冲突时停下让用户解决）。"""
    repo = registry.get_project(alias).path
    r = gitops.pull_rebase(repo)
    if r.conflict:
        err_console.print("[red]pull --rebase 冲突，已保留现场：[/red]")
        for f in gitops.unmerged_files(repo):
            err_console.print(f"  - {f}")
        err_console.print(f"[yellow]解决后重跑 overleaf-ctl sync {alias}[/yellow]")
        raise SystemExit(1)
    console.print(r.output)


@main.command()
@click.argument("alias")
@_handle_registry_errors
def push(alias: str) -> None:
    """git push。"""
    repo = registry.get_project(alias).path
    try:
        summary = gitops.push(repo)
    except gitops.GitError as exc:
        err_console.print(f"[red]push 失败：{exc}[/red]")
        raise SystemExit(1)
    console.print(summary)


@main.command()
@click.argument("alias")
@_handle_registry_errors
def status(alias: str) -> None:
    """打印工作区状态：dirty/clean、ahead/behind、冲突文件、rebase 进行中。"""
    proj = registry.get_project(alias)
    st = gitops.get_status(proj.path)
    console.print(f"[cyan]{proj.alias}[/cyan]  {proj.path}")
    console.print(f"  工作区: {'dirty' if st.dirty else 'clean'}")
    console.print(f"  ahead: {st.ahead}  behind: {st.behind}")
    if st.rebase_in_progress:
        console.print("  [yellow]rebase 进行中[/yellow]")
    if st.conflicts:
        console.print("  [red]冲突文件:[/red]")
        for f in st.conflicts:
            console.print(f"    - {f}")


@main.command(name="open")
@click.argument("alias")
@_handle_registry_errors
def open_cmd(alias: str) -> None:
    """用 VSCode 打开项目目录（code <path>）。"""
    repo = registry.get_project(alias).path
    # Resolve via which: on Windows the CLI is code.cmd, which a bare
    # subprocess spawn cannot find.
    code = shutil.which("code")
    if not code:
        err_console.print(
            "[red]找不到 VSCode CLI `code`。请在 VSCode 命令面板执行 "
            "“Shell Command: Install 'code' command in PATH”。[/red]")
        raise SystemExit(1)
    subprocess.run([code, repo])
    console.print(f"[green]已用 VSCode 打开 {repo}[/green]")


def _choose_main(alias: str | None, exc) -> str:
    """Interactive fallback for an ambiguous main file.

    Offers a numbered choice of the candidates and persists the pick to the
    registry (``main`` field) so the question is asked only once per project.
    Non-interactive callers (EOF on stdin) get the original error + exit 1.
    """
    candidates = getattr(exc, "candidates", None)
    if not candidates:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    console.print("[yellow]找到多个主文件候选：[/yellow]")
    for i, cand in enumerate(candidates, 1):
        console.print(f"  {i}. {cand}")
    try:
        idx = click.prompt("选择主文件编号",
                           type=click.IntRange(1, len(candidates)))
    except click.Abort:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    chosen = candidates[idx - 1]
    projects = registry.load_registry() if alias else {}
    if alias in projects:
        projects[alias].main = chosen
        registry.save_registry(projects)
        console.print(f"[green]已记住主文件 {chosen}（registry），下次自动使用。[/green]")
    return chosen


@main.command(name="compile")
@click.argument("alias", required=False)
@click.option("--path", "project_path", type=click.Path(exists=True, file_okay=False),
              help="Compile a local directory without registration or an Overleaf account.")
@click.option("--main", "main_override", default=None, help="主文件，覆盖 registry。")
@click.option("--engine", "engine_override", default=None,
              help="引擎 pdflatex|xelatex|lualatex，覆盖 registry。")
@click.option("--open", "open_pdf", is_flag=True, help="编译成功后打开 PDF。")
@click.option("--no-auto-install", "no_auto_install", is_flag=True,
              help="关闭缺包自动补。")
@_handle_registry_errors
def compile_cmd(alias: str | None, project_path: str | None, main_override: str | None, engine_override: str | None,
                open_pdf: bool, no_auto_install: bool) -> None:
    """本地 latexmk 编译（缺包自动补），可选 --open 打开 PDF。"""
    if bool(alias) == bool(project_path):
        raise click.UsageError("Provide exactly one project ALIAS or --path DIR.")
    proj = (Project(alias="local", path=str(Path(project_path).resolve()), remote="")
            if project_path else registry.get_project(alias))
    try:
        try:
            main_tex = compile_mod.detect_main(
                proj.path, override=main_override or proj.main)
        except compile_mod.AmbiguousMainError as exc:
            main_tex = _choose_main(alias, exc)
        # Build artifacts (incl. the produced PDF, under .outputs/) stay out of
        # sync via TEX_LOCAL_EXCLUDES. No bare "<stem>.pdf" pattern here: it
        # would match at ANY depth and silently hide a user's own root-level
        # reference PDF from git.
        gitops.ensure_local_excludes(proj.path, gitops.TEX_LOCAL_EXCLUDES)
        engine = engine_override or proj.engine or "pdflatex"
        result = compile_mod.compile_project(
            proj.path, main_tex, engine=engine, auto_install=not no_auto_install)
    except compile_mod.AmbiguousMainError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    except tex.TexNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        err_console.print("[yellow]请查看 README 的可选 TeX 依赖说明；CLI 安装器不安装 TeX。[/yellow]")
        raise SystemExit(1)
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    except gitops.GitError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    if result.installed:
        console.print(f"[cyan]自动安装：{', '.join(result.installed)}[/cyan]")
    if not result.ok:
        err_console.print("[red]编译失败，日志末尾：[/red]")
        err_console.print(result.log_tail)
        raise SystemExit(1)
    console.print(f"[green]编译成功：{result.pdf_path}[/green]")
    if open_pdf and result.pdf_path:
        _open_path(result.pdf_path)


@main.group(name="writing")
def writing_cmd() -> None:
    """本地写作档案与编号式 TeX 模板。"""


@writing_cmd.command(name="init")
@click.argument("alias", required=False)
@click.option("--path", "project_path", type=click.Path(exists=True, file_okay=False), help="直接使用本地 Git 项目根目录，无需登记或 Overleaf 远端。")
@click.option("--scaffold", is_flag=True, help="仅无现有 TeX 时创建 sections/ 模板。")
@click.option("--local-only", multiple=True, help="额外本地路径（不取消已跟踪文件）。")
@_handle_registry_errors
def writing_init(alias: str | None, project_path: str | None, scaffold: bool, local_only: tuple[str, ...]) -> None:
    import json
    if bool(alias) == bool(project_path):
        raise click.UsageError("Provide exactly one project ALIAS or --path DIR.")
    repo = project_path if project_path else registry.get_project(alias).path
    try:
        result = writing.initialize(repo, scaffold, list(local_only))
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@main.command(name="check-push")
@click.argument("alias")
@_handle_registry_errors
def check_push(alias: str) -> None:
    """检查暂存/跟踪文件和待推送历史；使用本地 upstream 快照，不联网。"""
    repo = registry.get_project(alias).path
    destination = publish.assert_publish_safe(repo)
    click.echo(f"Publication check passed for origin {destination} (local upstream snapshot).")
