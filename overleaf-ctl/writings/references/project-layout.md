# 项目布局与初始化

新论文优先使用用户提供的学校/会议/期刊模板。只有没有现有 TeX、用户要求从空项目开始时，运行 `overleaf-ctl writing init ALIAS --scaffold`；命令拒绝覆盖已有源文件或 sections 目录。

默认创建可编译的最小 article 工程：

```text
paper/
├── main.tex
├── references.bib
├── sections/
│   ├── 0_abstract.tex
│   ├── 1_intro.tex
│   ├── 2_related_work.tex
│   ├── 3_method.tex
│   ├── 4_experiments.tex
│   ├── 5_conclusion.tex
│   ├── 6_broader_impact.tex
│   └── X_appendix.tex
├── .writing/                 本地档案，禁止推送
│   ├── project.md
│   ├── outline.md
│   ├── progress.md
│   └── layout.json
└── .outputs/                 编译时创建，禁止推送
```

`main.tex` 默认输入摘要及 1–5；第 6 章、附录和 bibliography 的启用行初始为注释，按目标模板和真实内容需要启用。摘要文件只放摘要正文，abstract 环境由 main 持有。其他章节拥有各自 section 标题，main 只负责 input。模板不是投稿成品，也不提供虚构作者、数据或引用。`figures/`、`tables/`、模板资源等在实际使用时创建。

## 已有论文

保留 `sec/`、`sections/`、`1_introduction.tex`、`2_related.tex`、`4_experiment.tex` 等现有变体；不为了统一命名重命名或新增重复文件。读取真正的主文件及 input/include 链（包括嵌套 main）确定顺序；源代码里的注释、备用主文件和旧稿不能作为活动章节的依据。

若项目把 Related Work 合并进 Introduction，沿用它；若第 6 章是 Discussion 或 Limitation，也沿用它。六章编号是可调整的初始化约定，不是所有论文的结构要求。只有用户要求结构迁移时，才更新相关 input、引用、标签和编译配置。

## 本地档案

档案全部在单一 `.writing/` 下，按任务增量创建：

- `evidence-map.md`：证据与论点对应。
- `narrative.md`：按需记录核心价值、证据锚点与必须报告的事实。
- `blueprints/1_intro.md`：段落角色与证据顺序。
- `tasks/3_method.md`：章节任务包。
- `reviews/3_method.md`：规范与内容审查。
- `chapter-agents.md`：分工及交付记录。
- `data-manifest.md`：数据来源与图表/结论映射。
- `sources/`：仅本地阅读材料和摘录；正文 bibliography 在原项目 `.bib` 中。

不要把 `.writing/` 移到普通 `writings/`、`plan/` 或 `outputs/` 后仍假设它被自动保护。历史目录先检查、再迁移或显式配置本地路径，详见工具层。Git 忽略不会取消已跟踪文件；索引和待推送历史里的保留目录会触发阻止。
