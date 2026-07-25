# 版本迭代模板

> 本目录是新版本迭代的起始模板。`_` 前缀表示这不是真实版本。
>
> **当前阶段 A 仅占位。** 完整模板将在阶段 B 编写各 Skill 时一并填充（每个 Skill 负责自己的输出文件模板）。

## 使用方式（阶段 C 自动化前的手动版）

1. 复制整个 `_template/` 为目标版本号目录：
   ```powershell
   Copy-Item -Recurse d:\workspaces\ai\agent-base-busi-flow\templates\iterate\_template <目标项目>\iterate\v2.x.x
   ```

2. 删除目标目录中本 README，保留各阶段子目录占位

3. 按 [docs/workflow.md](../../../docs/workflow.md) 顺序逐 Skill 产出

## 阶段 B 待补充的模板文件

- `01-需求内容.md`（busi-req-analyze 输出模板）
- `clarify/01-需求澄清Q&A.md`（busi-req-clarify 输出模板）
- `接口文档/内部/01-{模块名}.md`、`接口文档/外部/{外部系统名}.md`（busi-api-spec）
- `design/design.html`（busi-design-doc）
- `dev-spec/00-AI开发规格书.md`、`dev-spec/01-{模块名}.md`、`dev-spec/qa/01-{模块名}-qa.md`（busi-dev-spec）
- `summary/迭代总结.md`（busi-iter-summary）
