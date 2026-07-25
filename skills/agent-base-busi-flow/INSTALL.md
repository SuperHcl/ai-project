# 安装与同步指南

> **BizFlow-8** 项目级安装：把 `skills/busi-*/` 复制到目标业务服务的 `.qoder/skills/`，让 Qoder 自动发现并触发。

## 目标

- 一键将本仓库 `skills/busi-*/` 同步到目标项目 `.qoder/skills/`（项目级 skill）
- **逐文件校验**目标项目 `.agent/` overlay（`AGENT.md` / `coding-rules.md` / `overlay-spec.md`）是否就绪
- 缺失时打印醒目提醒，支持 `-InitOverlay` 参数直接脚手架生成模板
- 输出可触发关键词清单

## 一键安装（推荐）

```powershell
powershell -ExecutionPolicy Bypass -File d:\workspaces\ai\agent-base-busi-flow\scripts\install.ps1 -TargetProject <目标项目根>
```

示例：

```powershell
# 装到 OCS 项目
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -TargetProject d:\workspaces\ai\ocs

# DryRun 仅打印不执行
.\scripts\install.ps1 -TargetProject d:\workspaces\ai\ocs -DryRun

# 强制覆盖（默认仅复制较新文件，幂等）
.\scripts\install.ps1 -TargetProject d:\workspaces\ai\ocs -Force

# 安装 + 初始化 overlay 模板（非交互式，适合 CI）
.\install.ps1 -TargetProject d:\workspaces\ai\ocs -InitOverlay
```

执行后：

- 11 个 BizFlow-8 skill 落到 `<目标项目>/.qoder/skills/busi-*/`（含 `busi-project-init`）
- Qoder 重新打开项目即可自动识别 skill
- 全部 trigger 关键词参见 [README.md 8 步流程速览](./README.md)

## Overlay 初始化（安装后必做）

`.agent/` 下的 3 个 overlay 文件是 skills 正常工作的前提。安装后如果检测到缺失，有两种初始化方式：

### 方式 A：AI 引导初始化（推荐）

在 Qoder 中打开目标项目，对 AI 说：

```
初始化项目
```

AI 会加载 `busi-project-init` skill，自动探测项目结构（模块、包路径、技术栈），交互式询问关键信息，生成带预填值的 overlay 文件。

### 方式 B：非交互式脚手架

重新运行安装脚本并加 `-InitOverlay` 参数：

```powershell
.\install.ps1 -TargetProject d:\workspaces\ai\ocs -InitOverlay
```

直接从模板目录复制骨架文件到 `.agent/`，所有项目特化值留 `<!-- TODO -->` 标记，需手动填充。

### 方式 A vs B 对比

| | 方式 A（AI 引导） | 方式 B（非交互式） |
|---|---|---|
| 预填值 | 自动探测包路径 / 模块结构 / 技术栈版本 | 全 TODO 标记 |
| 交互 | 逐项提问 + 推荐答案 | 无 |
| 适用场景 | 首次接入新项目 | CI / 批量初始化 |
| 产出质量 | 高（预填 + 用户确认） | 低（需手动补全） |

## 前置条件

1. 目标项目根目录存在（脚本会校验）
2. 推荐目标项目已具备 `.agent/AGENT.md` 等 overlay 文件（缺失会提醒并支持 `-InitOverlay` 初始化）
3. PowerShell 5+ / Windows 10+（已避开 GB18030 编码坑，脚本主体 ASCII-safe）

## 更新策略

通用仓库升级后，业务服务侧执行：

```powershell
cd d:\workspaces\ai\agent-base-busi-flow; git pull
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -TargetProject <目标项目根>
```

- `.qoder/skills/busi-*/` 默认增量覆盖（仅同步较新文件，robocopy `/XO`）
- `.agent/` overlay 不会被覆盖（属于业务服务侧资产）

## TODO（后续阶段）

- [ ] `scripts/new-version.ps1` 复制 `templates/iterate/_template/` 到 `iterate/v{版本号}`
- [ ] 用户级安装模式（跨项目共享，需配套 overlay 路径探测）
- [ ] CI 注入：业务服务 PR 自动校验 `.qoder/skills/` 与上游同步状态
