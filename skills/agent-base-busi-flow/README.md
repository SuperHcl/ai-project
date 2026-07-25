# agent-base-busi-flow（**BizFlow-8**）

> **BizFlow-8** = 通用 AI 业务开发流程仓 — Java/Spring 技术栈下的标准化 AI 协作开发 SOP，支撑"需求解析 → 澄清 → 接口文档 → 前置设计 → 编码 → 测试 → 沉淀"完整 8 步流程。
>
> 仓库名 `agent-base-busi-flow` 是物理仓库标识，沟通 / 文档 / PR 标签统一使用别名 **BizFlow-8**。

## 这是什么

一套**项目无关**的 AI 开发协作骨架，让 AI 在不同业务服务里都能按同一套流程办事：

- **rules/** — 跨项目通用的 Agent 行为准则
- **skills/** — 9 个标准流程 Skill（需求/澄清/接口/设计/规格/开发/编码规则/测试/沉淀 + 1 个总编排）+ 1 个项目初始化（`busi-project-init`）
- **templates/** — 版本迭代交付物模板（项目无关）
- **scripts/** — QuickStart 一键安装脚本

业务服务侧通过 `.agent/` overlay 注入项目特化内容（包结构、业务硬约束、领域知识），不污染通用仓库。

## 快速开始

```powershell
# 一键装到目标业务服务项目
powershell -ExecutionPolicy Bypass -File <path>\agent-base-busi-flow\scripts\install.ps1 -TargetProject <目标项目根>

# 示例（OCS）
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -TargetProject d:\workspaces\ai\ocs
```

执行后 11 个 BizFlow-8 skill 落到 `<目标项目>/.qoder/skills/`（含 `busi-project-init`），Qoder 重新打开即可自动识别触发。安装脚本会逐文件检测 `.agent/` overlay 是否就绪，缺失时提醒初始化。详见 [INSTALL.md](./INSTALL.md)。

## 目录结构

```
agent-base-busi-flow/
├── rules/AGENT.md                    硬性行为准则（自动加载）
├── skills/busi-*/SKILL.md            9 个流程 Skill（关键词触发）
├── templates/iterate/_template/      版本交付物模板
├── scripts/                          一键安装与版本初始化脚本
└── docs/                             流程总览与 overlay 写法指南
```

## 前置 + 8 步流程速览

| 步骤 | Skill | 触发词示例 |
|---|---|---|
| 0. 项目初始化 | `busi-project-init` | "初始化项目"、"init project" |
| 1. 解析需求 | `busi-req-analyze` | "解析需求"、"分析需求文档" |
| 2. 澄清交互 | `busi-req-clarify` | "澄清需求"、"需求拷问" |
| 3. 接口文档 | `busi-api-spec` | "接口文档"、"interface spec" |
| 4. 人类设计 | `busi-design-doc` | "设计文档"、"design doc" |
| 5. AI 规格书 | `busi-dev-spec` | "写规格书"、"dev spec" |
| 6. 编码 | `busi-dev-loop` + `busi-coding-rules` | "接口骨架"、"开始开发" |
| 7. 测试 | `busi-api-test` | "生成测试"、"接口测试" |
| 8. 总结沉淀 | `busi-iter-summary` | "迭代总结"、"沉淀" |
| 全流程 | `busi-flow-orchestrator` | "启动完整流程" |

> 步骤 0 是前置步骤，不属于 8 步流程链。安装后首次使用或新项目接入时执行，生成 `.agent/` overlay 文件后才能正常使用 B2-B9。

详细流程图见 [docs/workflow.md](./docs/workflow.md)。


## 设计哲学

- **上下文即稀缺资源** — Skill 只记 Agent 无法从代码推断的隐式知识
- **渐进式披露** — 关键词触发，不堆全量上下文
- **人工审查检查点** — 设计评审 / 接口骨架评审 / 测试通过 三道卡口
- **三条红线** — 先想再写、最小代码量、精准改动

## 文档

- [INSTALL.md](./INSTALL.md) — 一键安装与同步指南（`scripts/install.ps1`）
- [docs/workflow.md](./docs/workflow.md) — BizFlow-8 8 步流程总览图
- [CHANGELOG.md](./CHANGELOG.md) — 版本变更记录

> overlay 写法暂未单独成文，参考各 SKILL 末尾的"业务服务侧 overlay 必填 / 可补充"段。
