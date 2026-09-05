# overleaf-sync — 设计文档（spec）

- 日期：2026-06-06
- 状态：已通过 brainstorming，待用户复核 → 进入实现计划
- 作者：falcary + Claude

## 1. 目标与背景

把 Overleaf 的写作流变成「本地 VSCode 编辑 + git 双向同步 + 本地编译」，并把同步/编译动作封装成一个 robbyctl 风格的 CLI skill。

- 编辑：在 VSCode 里改本地 `.tex` 文件。
- 云端：Overleaf 项目（付费版，已开启 Git Integration）。
- 同步：`overleaf` 命令走 **Overleaf 原生 git**（`git.overleaf.com/<project-id>`）双向同步，冲突合并/增量交给 git。
- 编译：本地 **TinyTeX**（TeX Live 2025，对齐 Overleaf 的 pdflatex 引擎）跑 `latexmk` 出 PDF，缺包自动补。

### 已确认的关键决策（brainstorming 结论）

| 维度 | 决策 |
|---|---|
| Overleaf 账号 | 付费版，有 Git 入口 → 走原生 git |
| 同步机制 | Overleaf git over HTTPS + token |
| 本地编译 | v1 **包含**，用 TinyTeX（按需补包保证可编译） |
| 项目规模 | 多项目，CLI 维护 registry（别名表） |
| sync 语义 | **自动提交式**（类 Dropbox）：auto-commit → pull --rebase → push |
| 冲突 | **永远停下让用户手动解决，绝不自动覆盖** |
| 实现语言 | Python + click/rich（复刻 robbyctl 形态） |
| token 存储 | macOS Keychain（git credential helper），**绝不落盘到 registry / git config** |

## 2. 范围

### v1 包含
- 项目登记表（registry）与多项目管理
- git token 认证（存 Keychain）
- clone / register / list / sync / pull / push / status / open
- TinyTeX 安装（setup.sh 幂等）与 `compile`（latexmk + 缺包自动补）
- SKILL.md（教 Claude 触发/调用）+ README.md（robby-skills 门面风格）+ setup.sh

### 明确不做（YAGNI）
- Overleaf 实时/websocket 协同编辑（交给 VSCode 插件，非本 skill）
- 免费账号的 cookie/API 同步回退（本 skill 只服务付费版 git）
- Dropbox / GitHub bridge 同步
- PDF 实时并排预览（用 VSCode 或系统 PDF 阅读器）
- 多 Overleaf 账号 / 图形化冲突解决

## 3. 形态与目录结构

复刻 robbyctl（aistudio-jobs）那套：skill 目录里一个 Python click 包，装进 `.venv`，`pyproject.toml` 暴露 `overleaf` 命令，软链到 `~/.local/bin/`。

```
~/.agents/skills/overleaf-sync/
├── SKILL.md              # 触发条件 + 命令速查（给 Claude）
├── README.md             # 完整说明（robby-skills 门面风格，给人）
├── LEGAL.md              # 简短声明（可选，对齐 aistudio-jobs）
├── pyproject.toml        # console_script: overleaf = overleaf_sync.cli:main
├── requirements.txt      # click, rich
├── setup.sh              # 建 .venv + pip 装依赖（绕开坏镜像）+ 幂等装 TinyTeX
├── .venv/                # 隔离环境（.gitignore）
└── overleaf_sync/
    ├── __init__.py       # __version__ = "0.1.0"
    ├── cli.py            # click group + 各命令
    ├── registry.py       # projects.json 读写
    ├── gitops.py         # git 子进程封装：commit/pull --rebase/push/status/rebase 续接
    ├── auth.py           # token → Keychain（git credential approve）
    ├── tex.py            # TinyTeX 定位/安装/tlmgr 封装
    └── compile.py        # latexmk 编译 + 主文件探测 + 缺包自动补
```

- 全局命令：`~/.local/bin/overleaf` → `<skill_dir>/.venv/bin/overleaf`
- 依赖：仅 `click`、`rich`（公共 PyPI 有，setup.sh 用 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple` 绕开本机坏掉的 `~/.pip/pip.conf`）
- registry 用 JSON（stdlib，零额外依赖），不引 toml/yaml

## 4. 认证模型（Auth）

Overleaf 付费版 git 用 HTTPS + token：

- token 在 Overleaf **Account Settings → Git Integration → Create Token** 生成（形如 `olp_xxxx`）。
- clone 地址：`https://git.overleaf.com/<project-id>`。
- 认证：HTTPS Basic，username = `git`，password = token。
- 存储：交给 git credential helper（macOS 默认 `osxkeychain`），存一次后 pull/push 免输入。

`overleaf login` 流程：
1. 确保 `git config --global credential.helper osxkeychain`（没设就设）。
2. 隐藏输入读取 token（或从 stdin / `--token-stdin`）。
3. 用 `git credential approve` 把凭据写进 Keychain：
   ```
   printf 'protocol=https\nhost=%s\nusername=git\npassword=%s\n\n' "$HOST" "$TOKEN" | git credential approve
   ```
   `HOST` 默认 `git.overleaf.com`，可 `--host` 覆盖（为自建实例预留，但 v1 只验证 overleaf.com）。
4. 之后所有 git 操作自动从 Keychain 取凭据。
5. token 失效/更换：重跑 `overleaf login` 覆盖即可。

**安全底线**：token 只进 Keychain。registry、`.git/config`、日志里都不出现 token；不支持把 token 写进 remote URL。

## 5. Registry 与配置

文件：`~/.config/overleaf-sync/projects.json`（目录不存在则创建，权限 0700 / 文件 0600）。

```json
{
  "version": 1,
  "projects": {
    "mypaper": {
      "path": "/Users/falcary/overleaf/mypaper",
      "remote": "https://git.overleaf.com/PROJECT_ID",
      "main": "main.tex",
      "engine": "pdflatex"
    }
  }
}
```

- `path`、`remote` 必填；`main`、`engine` 可选（缺省时编译走自动探测 / pdflatex）。
- 别名（alias）是唯一 key。`clone`/`register` 写入，`list` 读出，其余命令按别名解析到 `path`。
- **不存 token。**

## 6. 命令参考（Command Reference）

所有针对单项目的命令，参数都是 `<别名>`；命令内部 `cd path` 或用 `git -C <path>`。

| 命令 | 签名 | 行为 |
|---|---|---|
| `login` | `overleaf login [--host H] [--token-stdin]` | 读 token → 存 Keychain（见 §4） |
| `clone` | `overleaf clone <url> <别名> [--path DIR]` | `git clone` 到 DIR（默认 `~/overleaf/<别名>`）+ 写 registry |
| `register` | `overleaf register <路径> <别名>` | 已有本地 git 仓库登记进 registry（校验是 git 仓库且 remote 指向 overleaf） |
| `list` | `overleaf list` | rich 表格：别名 / 路径 / 远端 / 状态（clean/dirty/ahead/behind） |
| `sync` | `overleaf sync <别名> [--no-commit] [--message M]` | **核心**，见 §7 |
| `pull` | `overleaf pull <别名>` | `git -C path pull --rebase` |
| `push` | `overleaf push <别名>` | `git -C path push` |
| `status` | `overleaf status <别名>` | 工作区状态 + ahead/behind + 冲突文件 |
| `open` | `overleaf open <别名>` | `code <path>`（VSCode 打开） |
| `compile` | `overleaf compile <别名> [--main F] [--engine E] [--open] [--no-auto-install]` | 本地 latexmk 编译，见 §8 |

> `--no-commit` / `--message` 是给「默认自动提交、偶尔想手动控制提交信息」留的口子；v1 默认行为是自动提交。

## 7. sync 算法（自动提交式）

输入：别名 → 解析 `path`。前置校验：是 git 仓库、有 overleaf remote。

```
1. 若存在未完成的 rebase（.git/rebase-merge | rebase-apply）：
     → 进入「续接模式」
     → 若仍有未解决冲突（git diff --name-only --diff-filter=U 非空）：
          打印冲突文件，提示「在 VSCode 解决后重跑 overleaf sync <别名>」，退出（非 0）
     → 否则 git rebase --continue，进入第 4 步（push）
2. 工作区有改动（git status --porcelain 非空）且非 --no-commit：
     git add -A
     git commit -m "overleaf-sync: <ISO 时间戳>"（或 --message）
3. git pull --rebase
     → 若 rebase 冲突：保留 rebase 现场（不 abort），
          打印冲突文件列表 + 解决指引，退出（非 0）。绝不自动覆盖。
4. git push
5. 打印摘要：本次提交、拉取了几个远端提交、推送结果、当前 clean
```

要点：
- `--no-commit` 且工作区有改动时：不自动提交，但脏工作区会让 `pull --rebase` 失败，故此情况下 sync **拒绝执行**并提示用户先 `git commit`/`git stash`（不擅自 stash）。
- 冲突时**不 abort、不 force**，保留现场让用户在 VSCode 解决；解决后再次 `overleaf sync` 自动 `--continue` 并 push。
- 时间戳由 Python `datetime` 生成（ISO 8601 本地时区）。
- 网络/认证失败：清晰报错并提示 `overleaf login`。

## 8. 本地编译（compile + TinyTeX）

### 8.1 TinyTeX 安装（setup.sh 幂等）
- 若检测不到可用 `latexmk`/`tlmgr`：
  ```
  curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh
  ```
  装到 `~/Library/TinyTeX`，二进制在 `~/Library/TinyTeX/bin/<arch>/`。
- 安装后确保关键工具：`tlmgr install latexmk`（及少量常用包，如 `latex-bin`、`xetex`）。
- 已有 TinyTeX 或系统已有 TeX（MacTeX）→ 跳过，不重复装。

### 8.2 工具定位（不依赖 shell PATH 重载）
按序探测 `latexmk` / `tlmgr`：
1. 当前 PATH（`shutil.which`）
2. `~/Library/TinyTeX/bin/*/`（glob）
3. `/Library/TeX/texbin/`（MacTeX）
找到即用绝对路径调用；都找不到 → 提示「跑 setup.sh 安装 TinyTeX」。

### 8.3 主文件探测
1. registry 里记的 `main`；或 `--main` 指定。
2. 否则扫项目根的 `.tex`：取同时含 `\documentclass` 与 `\begin{document}` 的那个。
3. 仍唯一不了 → 报错列出候选，要求用 `--main` 指定。

### 8.4 编译与缺包自动补
- 引擎：默认 `pdflatex`（对齐 Overleaf）；`--engine xelatex|lualatex` 覆盖；映射为 latexmk 开关（`-pdf` / `-xelatex` / `-lualatex`）。
- 命令：`latexmk <engine-flag> -interaction=nonstopmode -halt-on-error <main.tex>`，在项目目录里执行。
- **缺包自动补**（默认开，`--no-auto-install` 关）：
  1. 编译失败 → 读 `<main>.log`，匹配缺失文件：
     - `! LaTeX Error: File \`xxx.sty' not found.`
     - `! LaTeX Error: File \`xxx.cls' not found.`
     - 字体/`.fd` 缺失等
  2. 对每个缺失文件：`tlmgr search --global --file "/xxx.sty"` 拿到包名 → `tlmgr install <pkg>`。
  3. 重试编译。最多循环 N=5 次，避免死循环；补不上则把 latexmk 日志关键段落打给用户。
- 成功：打印产出 PDF 路径；`--open` 用系统默认程序打开（`open <pdf>`）。

## 9. setup.sh 职责
1. 在 skill 目录建 `.venv`（`python3 -m venv .venv`）。
2. `pip install -e .`（依赖 click/rich），用 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple` 绕开坏镜像。
3. 软链 `~/.local/bin/overleaf` → `.venv/bin/overleaf`。
4. 幂等安装 TinyTeX（§8.1）。
5. 打印后续步骤提示（`overleaf login` → `overleaf clone ...`）。

## 10. SKILL.md（给 Claude）
- frontmatter：`name: overleaf-sync` + `description`（触发词：overleaf、语雀外的「同步论文」、上传/下载/同步 tex、本地编译 latex、git.overleaf.com 链接等；并写清与其它 skill 的区分）。
- 正文：`<skill_dir>` 约定、环境自检（`overleaf --version`、软链重建）、命令速查、login/sync/compile 典型流程、冲突处理指引。
- 风格对齐 aistudio-jobs/SKILL.md。

## 11. README.md（给人，robby-skills 门面风格）
结构（镜像本机 aistudio-jobs/README.md 这一套 robby-skills house style）：
```
# overleaf
**Overleaf 本地同步 CLI** — 一句话定位 + headline 命令块
---
## Table of Contents
## 1. Architecture (1.1 Design Goal / 1.2 System Architecture[ASCII 图] / 1.3 Auth Model)
## 2. Installation (2.1 Install overleaf CLI / 2.2 Install TinyTeX)
## 3. Login
## 4. Quick Start (clone → sync → compile → open)
## 5. Command Reference (每命令一节)
## 6. Registry & Config (projects.json)
## 7. Local Compile (TinyTeX / pdflatex 对齐 / 缺包自动补)
## 8. Roadmap
## Releases (v0.1.0)
## Links (Overleaf git 文档 / TinyTeX)
```
> 若日后拿到 `shaojiahao.sjh/robby-skills` 原文，可再按它 1:1 精修。

## 12. 错误处理约定
- 未 `login` 就 clone/pull/push 报 401/403 → 提示先 `overleaf login`。
- 别名不存在 → 列出已登记别名。
- 不是 git 仓库 / remote 不是 overleaf → register 拒绝并说明。
- TeX 工具缺失 → 指向 setup.sh。
- 所有失败退出码非 0，错误信息走 rich 高亮。

## 13. 测试策略（实现阶段 TDD）
- **registry**：增删查、并发安全的读写、缺字段容错。
- **缺包日志解析**：喂若干真实 latexmk `.log` 样本，断言抽出的包名正确。
- **主文件探测**：多 `.tex` / 单 `.tex` / 无 `\begin{document}` 等场景。
- **gitops/sync**：用本地 bare 仓库模拟 overleaf 远端，覆盖 clean/dirty/ahead/behind/冲突/rebase 续接路径。
- **compile**：编译一个最小 `.tex` 出 PDF（需 TinyTeX）。
- **auth**：mock `git credential approve`，断言不写明文 token 到任何文件。

## 14. 未决/待验证（实现时确认）
- overleaf.com git 对 username 的要求（`git` vs 任意）——实现时用真实 token 验证一次。
- TinyTeX 默认是否自带 `latexmk`（不带就 setup.sh 补装）。
- `tlmgr search --global --file` 在 TinyTeX 上的可用性与输出格式。
