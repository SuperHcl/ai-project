# ⚠️ DEPRECATED — 本目录已被 BizFlow-8 install.ps1 取代

> **正式入口在 `<项目根>/.qoder/skills/`**（由 `agent-base-busi-flow/scripts/install.ps1` 一键安装）
>
> 本目录保留作为参考镜像，将随上游 `agent-base-busi-flow` 仓库更新。

## 这个目录是干什么的

`ocs/agent-base/` 是 [`agent-base-busi-flow`](https://gitlab.example.com/.../agent-base-busi-flow)（**BizFlow-8** 通用 AI 业务开发流程仓）在本项目的**平铺克隆副本**。

`ocs/.gitignore` 已忽略本目录（`agent-base/`），它**不属于 ocs 仓库**，是工作站本地 clone。

## 历史用途（v1：手工同步阶段）

在 `install.ps1` 落地之前（阶段 A），AI 通过 **AGENTS.md 引导直接读取本目录下的 SKILL.md**：

```
ocs/agent-base/skills/busi-design-doc/SKILL.md  ← AI 直接读这里
```

## 当前状态（v2：自动安装阶段）

阶段 A 完成后（参见 `agent-base-busi-flow/scripts/install.ps1`），改为：

```
1. 克隆/拉取 agent-base-busi-flow 到工作站任意位置
2. cd ocs && pwsh ../agent-base-busi-flow/scripts/install.ps1 -TargetProject .
3. AI 在 ocs 内自动识别 .qoder/skills/busi-* 触发流程
```

`.qoder/skills/` 才是 **AI 实际触发的 SSoT**。本目录的 `skills/` 子目录是历史副本，**不再被 AI 直接引用**。

## 为什么不直接删？

| 子目录 | 当前状态 | 原因 |
|---|---|---|
| `skills/` | ⚠️ DEPRECATED（由 install.ps1 同步到 .qoder/skills/） | 本目录的 skills 是上游副本，不是 AI 触发源 |
| `rules/` | ✅ 仍需 | install.ps1 v1 不接管 rules，目前还要手动引用 |
| `docs/` | ✅ 仍需 | 上游说明文档，未迁移 |
| `templates/` | ✅ 仍需 | iterate 模板，未迁移 |

`install.ps1` v2 计划接管 rules 与 templates，届时本目录可整体删除。

## 想升级 / 重新安装

```powershell
# 拉最新上游
cd <agent-base-busi-flow 路径>
git pull

# 重跑安装（增量同步，/XO 默认只覆盖更新的）
cd ocs
pwsh ..\agent-base-busi-flow\scripts\install.ps1 -TargetProject .
```

## 想知道有哪些 skill 可用

跑 `install.ps1` 末尾会输出 trigger map cheatsheet，或直接看 `.qoder/skills/` 目录列表。
