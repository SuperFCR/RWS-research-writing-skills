# RWS Research Writing Skills

[English](README.md) | **简体中文**

面向 Overleaf 和本地 LaTeX 项目的证据优先写作流程：保存项目记录、关联论点与文献、分章起草与审查。包含 **overleaf-ctl 0.3.1**。

## 功能

- **恢复进度：** 将要求、大纲和进度保存在 `.writing/`。
- **先证据后正文：** 起草前建立文献、论点与段落蓝图的对应关系。
- **分章审查：** 整篇起草时分派主要章节，再由主代理整合与审查。
- **清晰表达贡献：** 减少防御性措辞，保留不确定性与重要局限。
- **沿用论文结构：** 保留已有 `sections/` 或 `sec/` 布局，新论文可用编号 TeX 模板。

## 依赖

| 组件 | 用途 |
|---|---|
| Python ≥ 3.10，含 pip/venv；Git | CLI 与项目初始化 |
| `click`、`rich` | 自动安装至本地 `.venv` |
| LaTeX 引擎 + `latexmk` | 仅本地编译 PDF 时需要 |
| Node.js ≥ 18 / npm | 可选的 npm 包装器 |

阅读写作规则无需安装。推理、文献访问和子代理能力由使用技能的 AI 环境提供。

## 快速开始

macOS / Linux：

```bash
git clone https://github.com/SuperFCR/RWS-research-writing-skills.git
cd RWS-research-writing-skills
python3 overleaf-ctl/scripts/install.py --link-skill codex --link-cli
source overleaf-ctl/.venv/bin/activate
python3 overleaf-ctl/scripts/install.py --check
```

安装器将技能链接到 Codex，命令链接到 `~/.local/bin`，仅安装运行依赖。新终端中需激活虚拟环境，或将 `~/.local/bin` 加入 `PATH`。其他方式见 [Windows 与安装选项](overleaf-ctl/README.zh-CN.md#install)。

创建本地论文：

```bash
git init /path/to/paper
overleaf-ctl writing init --path /path/to/paper --scaffold
overleaf-ctl compile --path /path/to/paper --no-auto-install
```

编译需要 TeX。已有 Git 论文可跳过 `git init`，并去掉 `--scaffold`。Overleaf 项目先[登录并克隆](overleaf-ctl/README.zh-CN.md#use)，然后用 `$overleaf-ctl` 向代理提出写作或修订任务。

## 结构与本地文件

```text
overleaf-ctl/
├── SKILL.md      # 总入口
├── tools/        # CLI、Git 同步、编译、推送检查
└── writings/     # 档案、证据、起草、审查
```

论文的 `.writing/` 过程记录和 `.outputs/` 编译产物保留在本地。`overleaf-ctl sync/push` 还会检查暂存文件与待推送提交；直接 `git push` 或使用其他客户端会绕过检查。正文、文献库、模板和图表正常同步。

## 更新

在仓库根目录运行：

```bash
git pull --ff-only
python3 overleaf-ctl/scripts/install.py
python3 overleaf-ctl/scripts/install.py --check
```

[使用、排错与来源](overleaf-ctl/README.zh-CN.md) · [写作流程](overleaf-ctl/writings/SKILL.md) · [工具流程](overleaf-ctl/tools/SKILL.md)
