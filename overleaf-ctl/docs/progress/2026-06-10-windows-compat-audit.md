# Windows Compatibility Audit

Date: 2026-06-10
Status: 🔴 #1/#2/#3/#5 与 🟠 #6/#7 已于 2026-06-10 修复（平台分发实现，181 测试）；#4 setup.sh 与 #8/#9 仍为 macOS-only 已知项 — current product decision is **macOS-only** (README 使用前提)；Windows 协作者走裸 git。
Purpose: 逐点列出在 Windows 上会失效的位置、失效方式与修复方向，供未来决定是否支持 Windows 时直接开工；同时标出当前代码里"半吊子 win32 分支"的处置建议。

## 结论速览

- 代码里已有 `process.platform === "win32"` 分支（venv 的 `Scripts/python.exe` 路径），**给人"支持 Windows"的错觉，实际核心链路在 Windows 上全断**。
- 最严重的不是"不能用"，而是 **`login` 在 Windows 上有副作用**：会把用户全局 git 配置污染成不存在的 credential helper。
- 建议二选一：(A) 维持 macOS-only，删掉/注释 win32 分支并在 CLI 入口加平台检查直接报错；(B) 按下表逐项修，工作量集中在 auth / tex / cli 三处 + 安装层。

## 失效清单

### 🔴 核心功能失效（含副作用）

| # | 位置 | Windows 上发生什么 | 修复方向 |
|---|---|---|---|
| 1 | `overleaf_sync/auth.py:30` `ensure_credential_helper` 硬编码 `osxkeychain` | **有副作用的失效**：login 会执行 `git config --global credential.helper osxkeychain`，Windows 没有这个 helper → 之后所有 git 操作报 `credential-osxkeychain is not a git command`，token 永远存不住，且用户的全局 git 配置被污染（需手动清理才能恢复 Git Credential Manager） | 按平台选 helper：win → `manager`（Git for Windows 自带 GCM）、linux → `libsecret`/`cache`、mac → `osxkeychain`；或仅在 helper 未配置且平台为 mac 时设置 |
| 2 | `overleaf_sync/cli.py:324` `subprocess.run(["open", pdf])` | `compile --open` 抛 `FileNotFoundError`（Windows 无 `open` 命令）——编译成功但命令崩溃退出 | 三分支：win → `os.startfile(pdf)`、mac → `open`、linux → `xdg-open` |
| 3 | `overleaf_sync/cli.py:243` `subprocess.run(["code", repo])` | VSCode CLI 在 Windows 是 `code.cmd`；`subprocess` 不走 shell 解析不了 `.cmd` → `FileNotFoundError` | 用 `shutil.which("code")` 解析后调用（which 会带 PATHEXT 找到 code.cmd） |
| 4 | `setup.sh` 整体 | bash 脚本 + `install-bin-unix.sh`（TinyTeX 的 unix 安装器不支持 Windows）+ `~/Library` + `~/.local/bin` 全是 unix/mac 概念；原生 cmd/PowerShell 无法运行 | Windows 需要独立 `setup.ps1`：TinyTeX 用官方 `install-windows.bat`/zip（装到 `%APPDATA%\TinyTeX`），命令入口走 npm bin 而非 `~/.local/bin` |
| 5 | `overleaf_sync/tex.py:7-8` 回退路径 `~/Library/TinyTeX/bin/*` 与 `/Library/TeX/texbin` | PATH 上没有 latexmk 时彻底找不到工具（Windows TinyTeX 在 `%APPDATA%\TinyTeX\bin\windows\`；MiKTeX 另有路径）。`shutil.which` 那一层 OK（能找到 `latexmk.exe`） | 回退路径表按平台扩展：加 `%APPDATA%/TinyTeX/bin/windows`、MiKTeX 常见安装位 |

### 🟠 安装/工具链失效

| # | 位置 | Windows 上发生什么 | 修复方向 |
|---|---|---|---|
| 6 | `scripts/bootstrap-python.js:59` `PIP_CONFIG_FILE: "/dev/null"` | Windows 的 null 设备是 `NUL`；指向不存在路径时 pip 行为未定义（可能报错） | 用 `process.platform === "win32" ? "NUL" : "/dev/null"` |
| 7 | `bin/overleaf-ctl.js` + `scripts/bootstrap-python.js` 的 `pythonCandidates()` 只探测 `python3.13…python3` | Windows 官方安装器的命令名是 `python` / `py`，通常没有 `python3.x` 别名 → 探测全失败，报 "no Python >= 3.10" | 候选追加 `python`、`py`（`py -3` 需要特殊处理参数） |
| 8 | `package.json` `"test": "… && .venv/bin/python -m pytest -q"` | unix venv 路径硬编码；Windows 是 `.venv\Scripts\python.exe` → `npm test` 失败 | 测试入口改为 node 小脚本按平台解析 venv python |
| 9 | `scripts/link-skill.js` `fs.symlinkSync` | Windows 上创建 symlink 需要管理员权限或开发者模式，普通用户 `EPERM`；且 `~/.codex` `~/.claude` 在 Windows 的实际位置未验证 | symlink 失败时回退 junction（目录可用 `type: "junction"`，无需特权）或复制模式 |

### 🟡 大概率没事，待真机验证

| # | 位置 | 分析 |
|---|---|---|
| 10 | `gitops.py:136` `git -c core.editor=true rebase --continue` | `true` 不是 Windows 命令，但 git 通过自带的 sh 启动 editor，`true` 是 sh builtin → 预期可用；未在真机验证 |
| 11 | `detect_main` 返回的相对路径 | Windows 上 `str(Path)` 产生反斜杠（`T2V\main.tex`）；latexmk 能接受，但写进 registry 后该 registry 不能跨平台共享（实际场景 registry 本来就单机，影响小） |

### 🟢 本来就跨平台

- `registry.py`：pathlib + `os.replace` 原子写 ✓；`chmod 0600/0700` 在 Windows 近似 no-op 但不抛错 ✓；`~/.config` 路径可用（不合 Windows 惯例但 functional）。
- `gitops.py` 其余：纯 git 子进程，参数无 shell 依赖 ✓。
- `compile.py`：`os.pathsep` 拼 PATH、pathlib 路径运算 ✓。
- `auth.py` 的 `store_token`（`git credential approve` 走 stdin）机制本身跨平台 ✓ —— 只要 helper 选对（见 #1）。

## 当前建议（维持 macOS-only 的前提下）

1. **最低限度（防误伤）**：在 `cli.py` 的 `main` group 入口加平台检查——`sys.platform != "darwin"` 时对 `login/clone/sync/pull/push/compile/open` 打印「仅支持 macOS，Windows/Linux 协作者请用裸 git（见 README 使用前提）」并退出，避免 #1 这种**有副作用**的失效真的发生。
2. js 两处的 win32 venv 分支要么删除（诚实地 unix-only），要么保留并在 README 标注"仅为未来 Windows 支持预留，当前不可用"。
3. 若未来做 Windows 支持，按上表 #1→#9 顺序修，#1（credential helper）和 #2/#3（open/code）是纯 Python 小改，#4（安装层）工作量最大。

## 验证缺口

本审计基于代码走读，无 Windows 真机验证。若决定支持，需要在真实 Windows（含 Git for Windows + 官方 Python 安装器）上回归：login→clone→sync 全链路、TinyTeX Windows 安装器、npm link 权限。
