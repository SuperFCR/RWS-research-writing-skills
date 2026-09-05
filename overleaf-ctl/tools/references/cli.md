# overleaf-ctl — Overleaf Git-enabled 本地同步与编译 CLI

`overleaf-ctl` 把 Overleaf 写作流变成「本地 VSCode 编辑 + git 双向同步 + 本地 TinyTeX 编译」：

- **同步**走 Overleaf Git-enabled 项目的原生 git（`https://git.overleaf.com/<project-id>`）。这是 Overleaf premium integration 能力，不适用于没有 Git/GitHub integration 权限的免费项目。
- **编译**在本地用 TinyTeX（对齐 Overleaf 的 pdflatex 引擎）跑 `latexmk`，缺包自动 `tlmgr install` 补上。
- **sync 语义是自动提交式（类 Dropbox）**：auto-commit → `pull --rebase` → `push`。冲突时**永远停下让你手动解决，绝不自动覆盖**。

`overleaf-ctl --version` 应输出 **0.3.0**。

同步保护和新增 writing/check-push 命令以 [工具层入口](../SKILL.md) 为准；sync/push 指定 origin 的当前 upstream 分支，并检查本地记录泄漏。

## 环境准备

SKILL.md 中的 `<skill_dir>` 指本 skill 的安装目录（根入口 SKILL.md 所在目录，不是本参考文件目录）。Claude Code 触发 skill 时会告知 base directory，用它替换所有 `<skill_dir>`。

本机通常已把 `overleaf-ctl` 放到 PATH 上；优先直接使用命令，不要再回退到旧的 `overleaf` 命名。执行前确认一下：

```bash
overleaf-ctl --version    # 应输出 0.3.0

# 万一软链丢了/没装，重建：
test -x <skill_dir>/.venv/bin/overleaf-ctl || bash <skill_dir>/setup.sh
ln -sfn <skill_dir>/.venv/bin/overleaf-ctl ~/.local/bin/overleaf-ctl && overleaf-ctl --version
```

如果这个 skill 是作为 npm 包仓库使用，推荐安装路径是：

```bash
cd <skill_dir>
npm link
overleaf-ctl --version

# 当前 Python 环境缺 click/rich 时再跑：
npm run setup

# 缺 latexmk/tlmgr 或需要完整初始化 TinyTeX 时再跑：
npm run setup:full
```

环境依赖：

| 依赖 | 用途 | 处理方式 |
|---|---|---|
| Node.js >= 18 | npm wrapper / `npm link` | `node --version` 检查 |
| Python >= 3.10 | 运行核心 CLI | `python3 --version` 检查 |
| click / rich | CLI 参数和输出 | `npm run setup` 或 `pip install -e .` |
| git | clone/sync/pull/push | `git --version` 检查 |
| macOS Keychain + git credential helper | 保存 Overleaf token | `overleaf-ctl login` 会配置 |
| latexmk | 本地编译 | TinyTeX/MacTeX 提供 |
| tlmgr | 自动/手动补 TeX 包 | TinyTeX/MacTeX 提供 |

`setup.sh` 会在 skill 目录建 `.venv`、`pip install -e .`（依赖 `click`/`rich`，用清华镜像绕开本机坏掉的 `~/.pip/pip.conf`），软链全局命令，并幂等安装 TinyTeX。手动 pip 时请加 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`。

TeX 工具链支持 TinyTeX 和 MacTeX。优先推荐 TinyTeX，因为轻量且适合按需补包：

```bash
which latexmk || true
which tlmgr || true
ls ~/Library/TinyTeX/bin/*/latexmk 2>/dev/null || true
ls ~/Library/TinyTeX/bin/*/tlmgr 2>/dev/null || true

# 手动安装 TinyTeX
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh
~/Library/TinyTeX/bin/*/tlmgr install latexmk latex-bin xetex
```

MacTeX 也可以用，体积更大但包更全：

```bash
brew install --cask mactex
```

> ⚠️ **token 只进 macOS Keychain。** registry、`.git/config`、日志里都不出现 token。Overleaf git token 形如 `olp_xxxx`，在 Overleaf → Account Settings → Git Integration → Create Token 生成。

## 命令速查

```bash
overleaf-ctl login [--host H] [--token-stdin]            # 存 git token（已有凭据时打码显示并确认覆盖）
overleaf-ctl logout [--host H] [--yes]                   # 显示当前凭据（打码）并确认后删除
overleaf-ctl clone <url> <别名> [--path DIR]             # git clone（默认 ~/overleaf/<别名>）+ 登记 registry
overleaf-ctl register <路径> <别名>                       # 已有本地 git 仓库登记进 registry
overleaf-ctl list                                         # 表格：别名 / 路径 / 远端 / 状态
overleaf-ctl sync <别名> [--no-commit] [--message M]      # 核心：auto-commit → pull --rebase → push
overleaf-ctl pull <别名>                                  # git pull --rebase
overleaf-ctl push <别名>                                  # git push
overleaf-ctl status <别名>                                # 工作区状态 + ahead/behind + 冲突文件
overleaf-ctl open <别名>                                  # code <path>（VSCode 打开）
overleaf-ctl compile <别名> [--main F] [--engine E] [--open] [--no-auto-install]  # 本地 latexmk 编译
```

- 针对单项目的命令第一个参数都是**别名**；别名不存在时会列出已登记的别名。
- registry 在 `~/.config/overleaf-sync/projects.json`（目录 0700 / 文件 0600），只存 `path`/`remote`/`main`/`engine`，**不存 token**。

## 认证（一次性，token 进 Keychain）

```bash
overleaf-ctl login                       # 隐藏输入读取 token（推荐）
overleaf-ctl login --token-stdin         # 从 stdin 读 token（CI / 脚本）
echo "$OVERLEAF_TOKEN" | overleaf-ctl login --token-stdin
overleaf-ctl login --host git.overleaf.com   # 默认 host，自建实例可覆盖（v1 只验证 overleaf.com）
```

`login` 做两件事：确保 credential helper 已配置（按平台：mac→`osxkeychain`，win→`manager`，linux→`cache`），再把 `username=git` + `password=<token>` 喂给 `git credential approve` 写进 Keychain。之后所有 git 操作免输入。token 失效/更换：重跑 `overleaf-ctl login` 覆盖即可。

已登录时再次 `login` 会显示当前凭据（打码）并询问覆盖；`overleaf-ctl logout [--yes]` 删除凭据。

> 出现 `401`/`403`/`Unauthorized` → 提示先 `overleaf-ctl login`（或 token 过期，重跑 login 覆盖）。

## 典型流程

**首次接入一个 Overleaf 项目：**
```bash
overleaf-ctl login                                       # 1. 存 token（一次性）
overleaf-ctl clone https://git.overleaf.com/<项目id> mypaper   # 2. clone + 登记
overleaf-ctl open mypaper                                # 3. VSCode 打开开始写
```
⚠️ **URL 换算**：用户常给的是网页地址 `https://www.overleaf.com/project/<项目id>`——它**不能** clone。取其中 `<项目id>` 拼成 `https://git.overleaf.com/<项目id>` 再用。`--path DIR` 表示 DIR 就是项目根目录本身（不会再建别名子目录）。

已经在本地 clone 过的仓库，用 `overleaf-ctl register <路径> <别名>` 登记即可（会校验是 git 仓库且 remote 指向 overleaf）。

**日常同步（写完一轮）：**
```bash
overleaf-ctl sync mypaper                                # auto-commit → pull --rebase → push
overleaf-ctl sync mypaper --message "改 intro"            # 自定义提交信息
overleaf-ctl sync mypaper --no-commit                    # 不自动提交（要求工作区已 clean，否则拒绝执行）
```

**本地编译出 PDF：**
```bash
overleaf-ctl compile mypaper                             # 默认 pdflatex，缺包自动补，最多重试 5 次
overleaf-ctl compile mypaper --open                      # 编译后用系统默认程序打开 PDF
overleaf-ctl compile mypaper --main paper.tex --engine xelatex   # 指定主文件 / 引擎
overleaf-ctl compile mypaper --no-auto-install           # 关掉缺包自动补
```
主文件探测顺序：registry 里的 `main` / `--main` > 找同时含 `\documentclass` 与 `\begin{document}` 的 `.tex`（先扫根目录，根目录没有再递归扫子文件夹，跳过 `.git`/`.outputs`/`.writing`——子文件夹布局如 `T2V/main.tex` 开箱即用）。多个候选时交互式列编号让用户选，选择记入 registry 下次不再问；非交互场景报错列候选，用 `--main` 指定。缺 `latexmk`/`tlmgr` → 提示跑 `bash <skill_dir>/setup.sh` 装 TinyTeX。

编译产物统一写到项目内 `.outputs/`：`main.pdf`、`main.aux`、`main.log`、`main.bbl` 等都不再落在项目根目录；`.outputs/` 会写进 `.git/info/exclude`，`overleaf-ctl sync` 不会把它推到 Overleaf。

### TeX 缺包自动/手动处理

默认 `overleaf-ctl compile` 会自动补 TeX 包：`latexmk` 失败后读取 `.outputs/<main>.log` 和 `.outputs/<main>.blg`，解析缺失的 `.sty` / `.cls` / `.fd` / `.tfm` / `.bst` 文件，然后执行 `tlmgr search --global --file "/<missing-file>"` 找包名，再 `tlmgr install <package>`，最多重试 5 轮。

手动排查和补包：

```bash
overleaf-ctl compile mypaper --no-auto-install
tail -80 ~/overleaf/mypaper/.outputs/main.log
tail -80 ~/overleaf/mypaper/.outputs/main.blg 2>/dev/null || true

tlmgr search --global --file "/multirow.sty"
tlmgr install multirow

# TinyTeX 不在 PATH 时直接调用：
~/Library/TinyTeX/bin/*/tlmgr search --global --file "/multirow.sty"
~/Library/TinyTeX/bin/*/tlmgr install multirow
```

如果日志是 `File \`xxx.sty' not found`、`I couldn't open style file xxx.bst`、字体 metric 缺失，优先按上面查包安装。如果是 `Undefined control sequence`、`Missing $ inserted`、`Runaway argument`，通常是论文源码语法问题，不要误判成缺包。

## 冲突处理（sync 的关键路径）

`overleaf-ctl sync` **绝不 abort、绝不 force**。`pull --rebase` 遇冲突时保留 rebase 现场并退出（非 0），打印冲突文件：

1. 在 **VSCode 里逐个解决冲突文件**（搜 `<<<<<<<`），`git add` 标记已解决。
2. 重跑 `overleaf-ctl sync <别名>`：它检测到未完成的 rebase 会自动 `git rebase --continue` 然后 `push`。
3. 如果还有未解决冲突（`git diff --diff-filter=U` 非空），sync 会再次打印冲突文件并提示「解决后重跑 overleaf-ctl sync <别名>」。

绝不替用户 `git stash` 或丢弃改动。`--no-commit` 且工作区脏时，sync 直接拒绝并提示先 `git commit`/`git stash`。
