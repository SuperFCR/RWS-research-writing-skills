# overleaf-ctl 0.3.1

[English](README.md) | **简体中文**

LaTeX 写作技能，配套 Python CLI，支持本地编译与带推送检查的 Overleaf Git 同步。

```text
overleaf-ctl/
├── SKILL.md                 # 按任务加载 tools 或 writings
├── tools/overleaf_sync/     # Python CLI
├── tools/SKILL.md           # 同步与编译流程
├── writings/               # 档案、证据、起草、审查
├── scripts/                # 安装与技能链接
└── tests/                  # 单元与本地 Git 集成测试
```

<a id="install"></a>

## 安装

需要 **Python ≥ 3.10**（含 pip/venv）和已加入 `PATH` 的 **Git**。在本目录运行：

```bash
python3 scripts/install.py --link-skill codex --link-cli
source .venv/bin/activate
overleaf-ctl --version
python3 scripts/install.py --check
```

安装器创建 `.venv`，安装 `click ≥ 8.2` 和 `rich ≥ 13`；pip 在隔离构建环境中处理 `setuptools` 和 `wheel`。请保留包含 `tools/` 和 `writings/` 的完整技能目录。

- **命令入口：** 激活虚拟环境、调用 `.venv/bin/overleaf-ctl`，或将 `~/.local/bin` 加入 `PATH`。安装器不修改 shell 配置。
- **可选 npm：** 需要 Node.js ≥ 18；运行 `npm run setup`，再按需运行 `npm link` 和 `npm run link:skill:codex`。`setup.sh` 也调用同一 Python 安装器。
- **环境检查：** `--check` 只读，无需网络或凭据，单独报告缺少的可选 TeX 工具。

Windows PowerShell 使用已安装的 Python ≥ 3.10，例如：

```powershell
py -3.11 scripts/install.py --link-skill codex
.\.venv\Scripts\overleaf-ctl.exe --version
py -3.11 scripts/install.py --check
```

Windows 使用目录连接链接技能；`--link-cli` 仅用于 macOS/Linux。

### 可选 TeX 依赖

本地编译需要模板对应的 LaTeX 引擎和 `latexmk`，可由 TinyTeX、TeX Live、MacTeX 等发行版提供。CLI 安装器不安装 TeX。编译时若有 `tlmgr`，可自动补装缺少的 TeX 包；用 `--no-auto-install` 禁用。

<a id="use"></a>

## 使用

Overleaf Git 凭据与 GitHub SSH 认证相互独立：

```bash
overleaf-ctl login
overleaf-ctl clone https://git.overleaf.com/PROJECT_ID paper
overleaf-ctl writing init paper
```

已有 checkout 可用 `overleaf-ctl register /path/to/paper paper` 登记。本地项目无需 Overleaf 账号或远端：

```bash
git init /path/to/paper
overleaf-ctl writing init --path /path/to/paper
overleaf-ctl compile --path /path/to/paper --no-auto-install
```

已有 Git 项目可跳过 `git init`。新项目加 `--scaffold` 可创建编号 `sections/` 模板；存在 `.tex/.cls/.sty/.bst` 文件或章节目录时会拒绝生成。初始化不会推送。

```bash
overleaf-ctl list
overleaf-ctl status paper
overleaf-ctl compile paper --no-auto-install
overleaf-ctl check-push paper
overleaf-ctl sync paper --message "Revise introduction"
```

用 `$overleaf-ctl` 进入完整流程：项目档案、证据表、段落蓝图与两阶段审查。整篇起草时分派主要章节，局部修改保持局部范围。保留既有文件名与 input/include 链。详见[写作指令](writings/SKILL.md)、[项目布局](writings/references/project-layout.md)和 [CLI 参考](tools/references/cli.md)。

## 本地文件与推送检查

`.writing/` 保存项目记录，`.outputs/` 保存本地编译产物，通过 Git 的本地 `info/exclude` 排除。论文图表、模板和文献库正常参与同步。

`sync` 提交前检查索引和待暂存文件；`push` 获取目标分支后，检查每个待推送提交树，识别强制加入、加入后又删除的本地文件。发现问题会阻止发布，不删除文件或重写历史。直接 Git 命令、其他客户端和网页上传会绕过检查。

推送仅面向当前分支的 `origin` upstream，不自动携带 tags。缺少 upstream、推拉 URL 不一致或目标分支不存在时需先处理。`check-push` 使用本地 upstream 快照，实际推送会重新获取远端并检查。`sync` 会自动提交所有未忽略的改动，执行前应核对范围。

检查内容后，可精确排除其他本地目录：

```bash
overleaf-ctl writing init paper --local-only plan --local-only latex_outputs
```

路径记录在 Git 的 `info/overleaf-ctl-local-only.json` 中，不支持通配符。已跟踪文件会被报告，不会自动取消跟踪。Worktree 使用解析后的真实 Git 路径。

## 更新与排错

用 `git pull --ff-only` 更新源码，再运行 `python3 scripts/install.py` 和 `--check`。

- **找不到命令：** 激活虚拟环境或调用完整 CLI 路径；仅链接技能不会配置命令入口。
- **Python 太旧或缺少 venv：** 选择 Python ≥ 3.10，并通过系统包管理器补齐对应 venv 支持。
- **下载失败：** 安装器尊重已有 pip 配置，可传 `--index-url https://pypi.org/simple` 或可信镜像。
- **已有链接：** 在链接指向的安装上更新；安装器拒绝覆盖另一份安装。
- **缺少 TeX：** 单独准备所需 TeX 工具，重装 CLI 无法补齐。

## 开发

```bash
python3 scripts/install.py --dev
.venv/bin/python -m pytest -q
node scripts/link-skill.js codex --dry-run
npm pack --dry-run
```

`--dev` 安装测试依赖（`pytest`，Python < 3.11 时另装 `tomli`）。`npm test` 只运行测试，不安装依赖。`overleaf` 兼容命令别名继续保留。`docs/` 存放历史设计，以当前技能和代码为准。

0.3.1 已通过 **228 项测试**，并在 macOS 完成全新安装、技能与命令链接、本地论文初始化及 PDF 编译。测试使用临时本地 Git 远端；Windows/Linux 未作原生端到端验证。

## 参考来源

档案、证据与分章审查流程参考 [research-writing-skill](https://github.com/Norman-bury/research-writing-skill)，按现有 TeX 项目需求适配。贡献导向表达参考 [anti-defensive-writing-en](https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill/blob/main/skills/anti-defensive-writing-en/SKILL.md)，保留重要不利结果、不确定性与结论边界，并附上游 [MIT 许可](writings/references/anti-defensive-LICENSE.txt)。本包不会安装这两个上游技能。
