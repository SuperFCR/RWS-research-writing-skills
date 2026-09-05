# RWS Research Writing Skills

将 Overleaf/LaTeX 论文写作组织成可恢复的流程：项目档案 → 证据与段落蓝图 → 贡献主线与反防御性表达 → 分章写作 → 规范和内容审查。当前版本：**overleaf-ctl 0.3.1**。

本仓库同时包含 **Skill 指令**和 **Python CLI 工具**。只复制 `SKILL.md` 不会安装 CLI 依赖；完整使用请按下面的步骤安装。

## 依赖：哪些必须装

| 组件 | 何时需要 | 安装方式 |
|---|---|---|
| Python ≥ 3.10，含 pip/venv | 运行 CLI、初始化写作档案 | 先在系统中准备；macOS 自带 Python 可能太旧 |
| Git | 项目档案隔离、克隆和同步 | 先在系统中准备，并加入 PATH |
| `click ≥ 8.2`、`rich ≥ 13` | CLI 参数与输出 | 安装器自动装入本项目 `.venv`，不改系统 Python |
| `setuptools`、`wheel` | 构建本地 Python 包 | pip 在隔离构建环境中处理 |
| LaTeX 引擎 + `latexmk` | **本地编译 PDF 时才需要** | 使用已有 TinyTeX、TeX Live、MacTeX 等发行版 |
| `tlmgr` | TeX Live/TinyTeX 缺包自动补装 | 可选；其他发行版或不允许补包时用 `--no-auto-install` |
| Node.js ≥ 18 / npm | npm 包装器和 npm 安装方式 | **可选，下面的 Python 安装不需要** |
| `pytest`、兼容用 `tomli` | 维护者运行测试 | 安装时加 `--dev` |
| VSCode 的 `code` 命令 | `overleaf-ctl open` | 可选 |

论文推理、文献检索和子代理由使用本技能的 AI 环境提供；CLI 不捆绑模型、付费文献库或模型 API。只阅读/参考写作规则无需运行安装器。

## 首次安装（macOS / Linux）

先确认 `python3 --version` 至少是 3.10，且 `git --version` 可用。若默认 Python 太旧，把下方 `python3` 换成已安装的新版本命令，例如 `python3.11`。

```bash
git clone https://github.com/SuperFCR/RWS-research-writing-skills.git
cd RWS-research-writing-skills
python3 overleaf-ctl/scripts/install.py --link-skill codex --link-cli
source overleaf-ctl/.venv/bin/activate
overleaf-ctl --version
python3 overleaf-ctl/scripts/install.py --check
```

安装器建立 `overleaf-ctl/.venv`、安装 CLI 并验证依赖。`--link-skill codex` 把整个技能目录链接到 Codex 技能目录；`--link-cli` 在 `~/.local/bin` 链接命令。激活虚拟环境后无需额外 PATH 配置；跨终端使用时请确保 `~/.local/bin` 在 PATH，或直接调用 `.venv/bin/overleaf-ctl`。

默认不安装 TeX、不安装测试依赖、不登录账号，也不改 shell 配置。重复执行可更新当前源码的依赖；如果目标技能或命令已经指向另一份安装，脚本会拒绝覆盖，保留原安装供核对。

已有 GitHub SSH 认证，也可把 clone 地址换成 `git@github.com:SuperFCR/RWS-research-writing-skills.git`。

### Windows PowerShell

准备 Python ≥ 3.10 和 Git 后，在仓库根目录运行（示例选择 Python 3.11）：

```powershell
py -3.11 overleaf-ctl/scripts/install.py --link-skill codex
.\overleaf-ctl\.venv\Scripts\overleaf-ctl.exe --version
py -3.11 overleaf-ctl/scripts/install.py --check
```

Windows 使用目录连接链接技能；命令可直接通过上述 `.exe` 调用，或激活 `.venv\Scripts\Activate.ps1`。`--link-cli` 仅用于 macOS/Linux。本次实际安装与编译验证在 macOS 完成；Windows/Linux 分支未在原生系统上完整验证。

## 可选 TeX 依赖

只写作、整理证据、管理档案或同步源码时无需本地 TeX。需要 PDF 时，再准备目标模板要求的引擎（pdflatex/xelatex/lualatex）、`latexmk` 以及对应包。CLI 安装器、`setup.sh` 和 `npm run setup` 都不会安装 TeX。

```bash
python3 overleaf-ctl/scripts/install.py --check
overleaf-ctl compile ALIAS --no-auto-install
```

`--check` 只读检查，报告缺少的可选 TeX 工具；缺 TeX 本身不会使 CLI 环境检查失败。检查不访问凭据，也不连接 Overleaf。自动补 TeX 包仅在默认 `compile` 流程且存在 `tlmgr` 时可用，不要把 LaTeX 语法错误当成缺包。

## 第一个论文项目

已有 Overleaf Git 项目：

```bash
overleaf-ctl login
overleaf-ctl clone https://git.overleaf.com/PROJECT_ID paper
overleaf-ctl writing init paper
```

仅本地论文，无需 Overleaf 账号或远端（下例路径换成自己的论文目录）：

```bash
git init /absolute/path/to/paper
overleaf-ctl writing init --path /absolute/path/to/paper
# 有本地 TeX 工具链时：
overleaf-ctl compile --path /absolute/path/to/paper --no-auto-install
```

已有 Git 项目可省略 `git init`。空项目需要默认编号模板时加 `--scaffold`；检测到现有 `.tex/.cls/.sty/.bst` 或 `sections/` 时拒绝覆盖。初始化不会推送。源码仓库的 GitHub SSH 认证与 Overleaf 的 Git 凭据是两套独立的认证。

之后向 AI 提出论文写作/修订任务，使用 `$overleaf-ctl` 或 `$overleaf-writings` 进入相应流程。已有 `sections/`、`sec/` 及文件名保持不变；主文件与实际 input/include 链决定活动章节。

## 目录与同步边界

```text
RWS-research-writing-skills/
├── README.md                 安装入口
└── overleaf-ctl/
    ├── SKILL.md               技能总入口
    ├── tools/                 CLI、同步、编译、推送保护
    └── writings/              档案、证据、贡献主线、分章审查
```

论文项目中的 `.writing/` 保存过程记录，`.outputs/` 保存本地编译产物。它们在 Git 本地排除规则中隔离；`overleaf-ctl sync/push` 还会检查索引和待推送的每个提交，防止已跟踪或强制加入的记录误传。正文 TeX、BibTeX、模板和实际图表正常同步。直接 `git push` 或其他客户端不调用此保护。

备份仓库存放技能、源码和测试，不存论文、项目 registry、登录凭据、虚拟环境或写作档案。

## 更新与排错

在原来的源码 checkout 更新后，重跑安装器以同步依赖与版本：

```bash
git pull --ff-only
python3 overleaf-ctl/scripts/install.py
python3 overleaf-ctl/scripts/install.py --check
```

- `command not found`：激活 `.venv` 或使用其完整命令路径；只链接 Skill 不会把 CLI 加入 PATH。
- Python 太旧或缺 venv：使用 ≥ 3.10 的 Python，并通过系统包管理器补齐对应 venv 支持。
- pip 下载失败：安装器默认尊重已有 pip 配置；可显式传 `--index-url https://pypi.org/simple` 或自己信任的镜像，不会强制覆盖系统配置。
- 找不到 TeX 工具：按需准备 TeX 发行版；重复安装 CLI 不能解决缺少 LaTeX 引擎的问题。
- 目标链接已存在：检查它指向哪份源码，在该安装上更新；安装器不自动覆盖或删除另一份安装。

## 进一步阅读

- [技能入口](overleaf-ctl/SKILL.md)
- [工具层与发布保护](overleaf-ctl/tools/SKILL.md)
- [写作层](overleaf-ctl/writings/SKILL.md)
- [反防御性写作适配](overleaf-ctl/writings/references/anti-defensive.md)
- [维护者验证和详细使用](overleaf-ctl/README.md)

写作流程参考 research-writing-skill；反防御性模块强调证据支持的贡献，保留重要不利结果与结论边界。来源与许可见 [参考来源](overleaf-ctl/README.md#参考来源)。
