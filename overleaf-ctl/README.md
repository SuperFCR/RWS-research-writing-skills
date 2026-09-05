# overleaf-ctl 0.3.1

Overleaf/LaTeX 论文工作台：工具层负责本地编译与受保护的 Git 同步，写作层负责项目档案、证据、分章执行和审查。

## 结构

```text
overleaf-ctl/
├── SKILL.md                   总入口与按需路由
├── agents/openai.yaml         Codex 展示信息
├── tools/
│   ├── SKILL.md               工具流程与同步边界
│   ├── references/cli.md      认证、编译和冲突排错
│   └── overleaf_sync/         Python CLI 实现
├── writings/
│   ├── SKILL.md               写作流程
│   └── references/            文件模板、证据、章节任务与审查
├── bin/                       npm 兼容命令入口
├── scripts/                   安装与技能链接工具
├── tests/                     单元与本地 Git 集成测试
└── pyproject.toml             Python 包定义
```

根入口兼容 `$overleaf-ctl`。纯同步/编译只加载 tools，写作任务加载 writings；根目录保留原有 CLI 启动和安装入口，Python 包移至 `tools/overleaf_sync/`。原有 `overleaf-ctl` 命令及 `overleaf` 兼容别名仍保留。

## 接入与使用

安装前准备 Python ≥ 3.10（含 pip/venv）和 Git。在本目录运行：

```bash
python3 scripts/install.py --link-skill codex --link-cli
source .venv/bin/activate
overleaf-ctl --version
python3 scripts/install.py --check
```

这条路径无需 Node，默认只安装 CLI 运行依赖 click/rich；不安装 TeX 或测试依赖。pip 在隔离构建环境处理 setuptools/wheel，并尊重已有 pip 配置，可用 `--index-url` 显式选择源。安装器拒绝覆盖其他安装的链接。

Windows 可用 `py -3.11 scripts/install.py --link-skill codex`，然后调用 `.venv\Scripts\overleaf-ctl.exe`；不传 `--link-cli`。完整 Skill 目录需要与 tools/writings 一起保留。

npm 方式可选：`npm run setup` 调用同一个 Python 安装器，之后按需 `npm link` 和 `npm run link:skill:codex`。`setup.sh` 也是最小 CLI 安装入口；旧的自动 TeX 全量安装入口已移除。编译时另需 LaTeX 引擎和 latexmk，自动补包另需 tlmgr。

命令不在 PATH 时激活 venv，或使用 `.venv/bin/overleaf-ctl`；`--link-cli` 只创建 `~/.local/bin` 下的链接，不修改 shell 配置。`--check` 是无网络、无凭据访问的只读检查，缺少可选 TeX 工具不影响 CLI 就绪结果。

```bash
overleaf-ctl list
overleaf-ctl status ALIAS
overleaf-ctl writing init ALIAS             # 只补 .writing/，不改变 TeX
overleaf-ctl writing init --path /path/to/local-git-paper  # 不需要 Overleaf 远端
overleaf-ctl writing init ALIAS --scaffold  # 空项目才创建 sections/ 模板
overleaf-ctl compile ALIAS --no-auto-install
overleaf-ctl compile --path /path/to/local-paper --no-auto-install
overleaf-ctl check-push ALIAS               # 无网络预检
overleaf-ctl sync ALIAS --message "Revise introduction"
```

单项目命令使用已登记别名。已有 Overleaf Git 仓库可用 `register PATH ALIAS` 登记。初始化与写作不会自动推送。项目、凭据和已有论文保持在原位置，不随技能备份。

## 写作约定

- 在 `.writing/` 保存要求、大纲、进度和活动 TeX 清单；后续从这些记录恢复，并核对实际源码。
- 引言、相关工作及新增文献性论断先形成证据表和段落蓝图；引用存在不等于论断被支持。
- 证据整理后建立贡献主线，使用反防御性表达减少自贬与过程流水账，保留必要的不利结果和结论边界。
- 整篇起草/重写按主要章节分派独立子代理，主代理整合共享文件并做两阶段审查。局部修改保持局部范围。
- 正文直接写进活动 `.tex`，保留用户既有 `sections/`、`sec/` 和文件名，不生成平行 Markdown 章节或额外 LaTeX 工程。
- 新模板为 `main.tex`、`references.bib` 和 `sections/0_abstract.tex` 至 `6_broader_impact.tex`，附 `X_appendix.tex`。第 6 章、附录和 bibliography 按实际需要启用；有现有 .tex/.cls/.sty/.bst 模板时拒绝覆盖。

详见 [写作层](writings/SKILL.md) 和 [项目布局](writings/references/project-layout.md)。质量审查由代理结合实际资料完成，CLI 的检查不证明学术结论正确。

## 本地文件与推送

默认保留 `.writing/` 和 `.outputs/` 为本地目录，在 Git 的 `info/exclude` 中排除。正文图表、模板和 `.bib` 正常参与同步，不对所有 PDF、`figures/`、`tables/` 或 `refs/` 做宽泛排除。

`sync` 的自动提交会检查索引及将被暂存的文件。`push` 检查索引，获取实际目标分支，再检查每个待推送提交树；包括强制加入、已跟踪、加入后又删除的本地文件。发现问题会阻止，不删除本地副本、不取消跟踪、不重写历史。

发布只发送当前分支 `HEAD` 到它的 `origin` upstream 分支，禁用自动携带 tags；无 upstream、推送和拉取 URL 不一致或目标分支不存在时拒绝猜测。`check-push` 只用本地 upstream 快照，实际推送会重新获取远端并复检。

旧本地目录可在检查内容后精确排除：

```bash
overleaf-ctl writing init ALIAS --local-only plan --local-only latex_outputs
```

配置保存在 Git 内部 `info/overleaf-ctl-local-only.json`。不支持通配符，不会自动迁移或取消跟踪。Git worktree 通过真实 Git 路径处理共享 exclude 和配置。

直接 `git push`、其他 Git 客户端和网页上传不调用本工具保护；论文发布工作流统一使用 `overleaf-ctl sync/push`。排除目录不能代替修改范围审查，sync 仍会自动提交所有未被忽略的改动。

## 验证

```bash
python3 scripts/install.py --dev
.venv/bin/python -m pytest -q
node scripts/link-skill.js codex --dry-run
npm pack --dry-run
```

`--dev` 才安装 pytest 等测试依赖，`npm test` 仅运行测试，不会先改环境或联网安装。

0.3.1 复查：228 项测试通过；macOS 全新虚拟环境完成最小依赖安装、技能/命令链接、环境检查、本地论文初始化和实际 PDF 编译。默认安装未包含 pytest，也未触发 TeX 安装。三个技能入口、相对引用与 npm 包清单检查通过。Windows/Linux 原生安装未作完整实测。

测试使用本地临时 bare Git 仓库，不连接真实 Overleaf。旧版本设计文档保留在 `docs/` 作为历史记录，以当前技能和代码为准。

## 参考来源

写作流程参考 [Norman-bury/research-writing-skill](https://github.com/Norman-bury/research-writing-skill) 的档案、证据和分章审查思路，按现有 TeX 与本地隔离需求重新实现，没有安装该仓库。反防御性模块参考 [Adkid-Zephyr/anti-defensive-writing-en](https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill/blob/main/skills/anti-defensive-writing-en/SKILL.md)，进行了证据边界适配，并保留上游 MIT 许可。
