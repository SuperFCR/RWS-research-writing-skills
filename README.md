# RWS Research Writing Skills

以现有 Overleaf/LaTeX 论文为中心的写作技能与工具备份，当前版本 **overleaf-ctl 0.3.0**。

```text
RWS-research-writing-skills/
└── overleaf-ctl/
    ├── SKILL.md
    ├── tools/       同步、编译、初始化与推送保护
    └── writings/    档案、证据、贡献主线、分章执行与审查
```

- [技能入口](overleaf-ctl/SKILL.md)
- [工具层](overleaf-ctl/tools/SKILL.md)
- [写作层](overleaf-ctl/writings/SKILL.md)
- [反防御性写作适配](overleaf-ctl/writings/references/anti-defensive.md)
- [安装、用法与验证](overleaf-ctl/README.md)

论文正文保持在原有 `sections/` 或 `sec/` 中；新项目支持编号式章节模板。写作过程文件集中在本地 `.writing/`，构建产物在 `.outputs/`。CLI 同步除了本地忽略，还检查索引及待推送的每个提交，防止本地记录误传 Overleaf。

反防御性表达用于突出有证据的贡献、减少自我贬低与过程流水账，同时保留必要的不利结果与结论边界。整篇起草按主要章节分派独立子代理，主代理做规范和内容审查。

本仓库存储技能、工具源码和测试；不包含论文项目、登录凭据、项目 registry、虚拟环境或本地写作记录。

验证：205 项完整回归测试及 4 项补充 Git 发布测试通过（共 209 项）；新模板经实际 latexmk 编译通过；三个技能入口校验、相对引用和 npm 打包清单检查通过。质量规则还需结合真实研究材料执行，自动化测试不证明论文结论正确。

参考来源与上游许可见 [overleaf-ctl README](overleaf-ctl/README.md#参考来源)。保留本仓库原有 LICENSE 及上游反防御性技能的 MIT 许可。
