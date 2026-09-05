# overleaf-ctl 0.3.0

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

已有安装先使用 `overleaf-ctl --version` 检查，版本应为 `0.3.0`。从仓库接入时，在本目录运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
node scripts/link-skill.js codex
.venv/bin/overleaf-ctl --help
```

也可沿用 `npm run setup`、`npm link`。这些路径需要 Python >= 3.10；npm 路径另需 Node >= 18。安装脚本与平台细节见 [CLI 参考](tools/references/cli.md)。编译需要已有 LaTeX 工具链，只有相应请求才运行完整环境安装。

```bash
overleaf-ctl list
overleaf-ctl status ALIAS
overleaf-ctl writing init ALIAS             # 只补 .writing/，不改变 TeX
overleaf-ctl writing init ALIAS --scaffold  # 空项目才创建 sections/ 模板
overleaf-ctl compile ALIAS --no-auto-install
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
- 新模板为 `main.tex`、`references.bib` 和 `sections/0_abstract.tex` 至 `6_broader_impact.tex`，附 `X_appendix.tex`。第 6 章、附录和 bibliography 按实际需要启用；有现有 TeX 或模板时拒绝覆盖。

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
.venv/bin/python -m pytest -q
node scripts/link-skill.js codex --dry-run
npm pack --dry-run
```

测试使用本地临时 bare Git 仓库，不连接真实 Overleaf。旧版本设计文档保留在 `docs/` 作为历史记录，以当前技能和代码为准。

## 参考来源

写作流程参考 [Norman-bury/research-writing-skill](https://github.com/Norman-bury/research-writing-skill) 的档案、证据和分章审查思路，按现有 TeX 与本地隔离需求重新实现，没有安装该仓库。反防御性模块参考 [Adkid-Zephyr/anti-defensive-writing-en](https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill/blob/main/skills/anti-defensive-writing-en/SKILL.md)，进行了证据边界适配，并保留上游 MIT 许可。
