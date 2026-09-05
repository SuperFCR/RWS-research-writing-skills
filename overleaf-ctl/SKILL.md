---
name: overleaf-ctl
description: 在 Overleaf 或本地 LaTeX 论文项目中写作、修订、组织章节与证据，或使用 overleaf-ctl 同步和编译。支持已有 sections/sec 布局、本地写作档案和推送隔离；纯同步编译只加载 tools。
---

# Overleaf 论文工作台

这是一套两层技能：`tools/` 提供 CLI、同步保护和编译；`writings/` 组织论文档案、证据、章节执行与审查。正文直接编辑论文现有 `.tex` 文件。

`<skill_dir>` 指本文件所在安装目录；通过符号链接加载时，按真实目录解析相对路径。CLI 版本为 `0.3.0`，原有命令继续可用。

## 按请求加载

- 克隆、登记、拉取、推送、冲突、编译或工具故障：读 [tools/SKILL.md](tools/SKILL.md)。纯工具任务不创建写作档案。
- 起草、修订、文献论证、章节规划、新论文初始化或继续之前写作：读 [writings/SKILL.md](writings/SKILL.md)。需要编译或同步时再读工具层。
- 技能维护：实现代码在 `tools/overleaf_sync/`，CLI 入口和安装脚本保留在根目录，测试在 `tests/`。

## 项目边界

论文源文件（`main.tex`、`sections/` 或 `sec/`、`.bib`、模板、正文图表）属于可同步内容。写作过程文件集中在 `.writing/`，本地编译产物在 `.outputs/`。不要把本技能目录复制到论文项目里，也不要额外生成平行的 `chapters/`、`plan/`、`latex-output/` 工程。

写作请求本身不代表要推送。用户已要求同步时，在完成相应检查后直接用 `overleaf-ctl sync/push` 执行；保留既有授权，不重复确认。只在证据、必要输入或实际冲突阻碍当前工作时询问，继续不依赖该输入的工作。
