# Changelog

记录 **BizFlow-8**（`agent-base-busi-flow`）通用 AI 流程仓的版本演进。语义化版本：MAJOR.MINOR.PATCH。

> 仓库别名 **BizFlow-8** = 业务流（BusinessFlow）+ 8 步流程。沟通 / 文档 / PR 标签优先用别名，物理仓库名 `agent-base-busi-flow` 仅用于克隆 / 路径引用。

## [Unreleased]

### 2026-07-21：项目 overlay 初始化 Skill + 安装脚本增强

**新增 `busi-project-init` Skill**
- 前置 Skill，不属于 B2-B9 流程链，安装后首次使用或新项目接入时触发
- 检测 `.agent/` 下 3 个 overlay 文件（`AGENT.md` / `coding-rules.md` / `overlay-spec.md`）是否就绪
- 缺失时自动探测项目结构（模块、包路径、技术栈），交互式询问关键信息，生成带预填值的 overlay 文件
- 3 个 overlay 模板文件：`references/AGENT.md.template` / `coding-rules.md.template` / `overlay-spec.md.template`

**`install.ps1` 增强**
- 新增 `-InitOverlay` 参数：非交互式脚手架生成 overlay 模板（适合 CI）
- step [2/4] → [2/5] 逐文件检测 overlay（原来只检查 `.agent/` 目录是否存在）
- 新增 step [4/5]：缺失时打印醒目提醒块，提供两种初始化方式（AI 引导 / 非交互式）
- trigger map 新增 `busi-project-init` 行

**文档同步更新**
- README.md：流程速览表新增步骤 0（项目初始化），skill 数 10 → 11
- INSTALL.md：新增「Overlay 初始化」专节，含方式 A（AI 引导）vs 方式 B（非交互式）对比表
- rules/AGENT.md §11：新增 `busi-project-init` 前置说明
- docs/workflow.md：新增「前置步骤」章节 + 触发词速查表补充

### 2026-06-16：BizFlow-8 命名 + 一键安装 + 模板抽离（阶段 B → C → E）

**B：handoff skill 试用**
- `ocs/.qoder/skills/handoff/` 新增 handoff skill（移植自 `kgd-doc/skills/handoff`），含 OCS BizFlow-8 适用补充字段（bizflow_stage / bizflow_module / bizflow_version）

**A：scripts/install.ps1 项目级一键安装**
- 新增 `scripts/install.ps1`（166 行 ASCII-safe，规避 PowerShell 5.1 GB18030 解析坑）
- 参数 TargetProject / Force / DryRun，robocopy `/XO` 增量幂等
- 5 步流程：路径解析 → 枚举 busi-* → 校验 `.agent` overlay → 复制 → 输出 trigger map cheatsheet
- README.md 标题加 BizFlow-8 别名 + 快速开始可执行命令；INSTALL.md 重写为可执行一键安装文档
- 验证：10 个 BizFlow-8 skill 装到 `ocs/.qoder/skills/`

**C：模板抽离 SSoT（5 个 skill 瘦身 39%）**
- 5 个 skill 内嵌模板抽到独立 `references/*.template.md`：
  - busi-design-doc：259 → 119 行（-54%）
  - busi-dev-spec：279 → 117 行（-58%）
  - busi-api-spec：234 → 165 行（-29%）
  - busi-iter-summary：243 → 149 行（-39%）
  - busi-api-test：249 → 219 行（-12%）
- 累计：1264 → 769 行（**-39%**），SKILL.md 触发即吃上下文密度提高 2.2×
- `ocs/agent-base/skills/README.md` 加 DEPRECATED 标记，澄清 install 后目录分层（skills 由 `.qoder/skills/` 取代；rules / docs / templates 仍需手工同步）

**E：BizFlow-8 命名统一收尾**
- CHANGELOG / `rules/AGENT.md` / `docs/workflow.md` 顶部统一标注 BizFlow-8 别名
- 清理 README.md 中"阶段 C 落地"占位与不存在的 `docs/overlay-guide.md` 悬挂引用

### 阶段 A：仓库骨架（已完成，commit f0d351b）

- 初始化仓库目录结构
- 添加 `rules/AGENT.md` 通用行为准则
- 添加 `docs/workflow.md` 8 步流程总览
- 添加 9 个 `skills/busi-*/SKILL.md` 占位文件
- 添加 `templates/iterate/_template/` 模板目录占位

### 决策留痕

- 阶段 C 试跑目标业务服务：**ocs（海外报关）** — 路径 `d:\workspaces\ai\ocs\`，Maven 多模块结构（ocs-common / ocs-feign / ocs-server）
