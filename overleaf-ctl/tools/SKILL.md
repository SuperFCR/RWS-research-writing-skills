---
name: overleaf-tools
description: 使用 overleaf-ctl 管理 Overleaf Git 项目的克隆、登记、双向同步、冲突和本地 LaTeX 编译；检查并阻止本地写作档案或构建目录进入推送。
---

# 工具层

先用 `overleaf-ctl --version` 和 `overleaf-ctl list` 确定版本与项目别名。当前实现是 `0.3.1`。命令可用时直接使用；不要自动重装环境或再次登录。命令缺失时先检查上级安装目录的 `.venv` 命令与 [README](../README.md#接入与使用)，用 `scripts/install.py --check` 区分缺依赖和缺 PATH；安装器默认不安装 TeX。完整命令、认证和编译排错按需读取 [references/cli.md](references/cli.md)。其中 `<skill_dir>` 指上一级根目录。

## 常用命令

```bash
overleaf-ctl status ALIAS
overleaf-ctl pull ALIAS
overleaf-ctl compile ALIAS --no-auto-install
overleaf-ctl compile --path /absolute/path/to/local-paper --no-auto-install
overleaf-ctl check-push ALIAS
overleaf-ctl sync ALIAS --message "Describe the manuscript changes"
overleaf-ctl push ALIAS
```

`compile --path` 与登记别名二选一，不读取项目 registry，也不要求 Overleaf 账号。默认 `compile` 可自动补 TeX 包；`--no-auto-install` 用于环境已齐全或用户不希望安装依赖的情况。主文件与引擎沿用项目配置，多个候选时根据上下文选择并显式传 `--main`；确实无法确定时再问。主文件探测跳过 `.writing/` 和 `.outputs/`。

## 推送隔离

`sync` 保持自动提交 → pull/rebase → push 的原有行为，但新版本执行以下保护：

1. 在 Git 的本地 `info/exclude` 排除 `.writing/`、`.outputs/` 和既有 TeX 中间文件，支持普通仓库及 Git worktree。
2. 自动提交前后检查索引：保留目录内的已跟踪或强制暂存文件会阻止提交。
3. `push` 再检查索引及待发送的每个提交树；先加入后删除的本地记录仍会被发现。
4. 仅向当前分支的 `origin` upstream 分支发送 `HEAD`，关闭自动携带 tags，避免其他 push 配置扩大范围。缺失或非 origin upstream 时说明配置问题。

`check-push` 是使用本地 upstream 快照的无网络预检，不代替 diff 审查或编译，也不验证论文论证质量。实际推送前会 fetch 目标分支后再次检查，且要求 origin 的单一推送 URL 与拉取 URL 一致；常规 Git 的冲突和非快进保护仍有效。

出现阻止提示时读取列出的路径和提交，保留本地文件。普通忽略规则不会取消跟踪。不要自动删除文件、批量 `git rm`、重写历史、force push 或绕过保护；先准备范围明确的迁移/取消跟踪方案。不要盲目反复 sync，前一轮可能已创建本地提交。

本保护属于 `overleaf-ctl` CLI，直接运行 `git push`、其他客户端或网页上传不会调用它。因此本工作流的发布入口始终使用 `overleaf-ctl sync/push`。

## 历史本地目录

新记录只放 `.writing/`。旧项目若有 `plan/`、`latex_outputs/` 等本地目录，先检查内容和 Git 跟踪状态；可迁移到 `.writing/`，或确认用途后添加精确本地路径：

```bash
overleaf-ctl writing init ALIAS --local-only plan --local-only latex_outputs
```

配置保存在 Git 内部 `info/overleaf-ctl-local-only.json`，不会上传。不支持通配符。命令不删除、移动或取消跟踪旧文件；已跟踪时会阻止并报告。不要笼统忽略 `figures/`、`tables/`、`refs/`、`outputs/` 或所有 PDF，这些可能是正常论文依赖。

同步前检查 diff 和文件清单，注意 `sync` 会自动提交所有未忽略的改动。只发布当前授权范围内的文件；如果存在无关改动，先确定归属，不能把目录忽略当作修改范围审查的替代品。

冲突时保留 rebase 现场，定位并解决具体冲突；无未解决冲突后再继续。认证令牌只走现有系统凭据库，不写入论文、档案或日志。
