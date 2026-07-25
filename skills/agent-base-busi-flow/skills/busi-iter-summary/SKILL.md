---
name: busi-iter-summary
description: "版本收尾总结（8 步流程第 8 步）。完整性审计 B2-B8 产物 → 生成 CHANGELOG 段落 → 沉淀遗留待澄清 → AI 自反思踩坑 → 统一 git push。第五道（也是最后）人工审查检查点：版本发布前最后把关。"
next_skills: []
---

# 版本收尾总结

## 定位

**8 步流程的第 8 步，也是终点**。前 7 步关注"做对单个版本"，第 8 步关注"沉淀给下个版本"。

> **本 Skill 不是实时同步检查清单**——那已经分散到 B5/B6/B7/B8 的内置自检里。本 Skill 是"全部做完后的体检报告 + 知识沉淀 + 推送上线"。

5 个职责：

1. **完整性审计** — B2-B8 产物是否齐？接口文档与代码是否一致？
2. **CHANGELOG 生成** — 基于 commit history + B2 需求清单 + B5 设计变更，自动汇成版本变更段
3. **遗留沉淀** — B2/B3/B5/B7 的 ⚠️ 标记是否全清？未清的进下版本待办
4. **AI 自反思** — `develop/qa/00-debug-log.md` 踩坑沉淀到下版本预防清单
5. **统一 push** — B7 只 commit 不 push，由本 Skill 统一推送（避免半成品上 main）

## 输入

- `iterate/v{版本}/{业务模块}/` 下本模块全部产物（B2/B3/B4/B5/B6/B7/B8）
- 业务代码仓 git history（`git log v{上一版本}..HEAD --oneline`）
- 业务代码 git diff（`git diff v{上一版本}..HEAD --stat`）

## 输出

```
iterate/v{版本}/{业务模块}/
├── 05-版本收尾.md       ← 本模块收尾主文档（含收尾总结 + 遗留 + 自反思）
└── CHANGELOG-fragment.md ← 给项目 CHANGELOG.md 追加的模块段落
```

并更新（如存在）：
- 项目根 `CHANGELOG.md`（追加 v{版本}/{业务模块} 段落）
- `iterate/v{下个版本}/{业务模块或新模块}/01-需求内容.md`（追加遗留 ⚠️ 项作为预定义需求 0）

---

## 五段流程

### 段 1：产物完整性审计

逐项检查并产出审计表（不通过 → 立即返回对应 Skill 补齐，禁止跳过）：

| # | 必须存在的产物 | 检查方式 | 缺失则返回 |
|---|---|---|---|
| 1 | `01-需求内容.md` | 文件存在 + 第六章 ⚠️ 已清 / 已转移 | B2/B3 |
| 2 | `02-接口文档-内部.md` / `02-接口文档-外部.md` | 与代码 Controller / Feign 注解一一对应 | B4 |
| 3 | `03-设计文档.md` | 本模块一篇，10 节齐 | B5 |
| 4 | `04-AI开发规格书.md` | 本模块一篇，7 节齐 | B6 |
| 5 | git commit 序列 | `git log` 数量 ≥ 需求数（按需求拆 commit） | B7 |
| 6 | `qa/0{n}-{需求}-TEST-SPEC.md` + 测试代码 | TEST-SPEC + 测试用例齐 | B8 |
| 7 | `qa/` Q&A 归档 | 编码期 Q&A 已落盘 | B7 |

**接口文档与代码一致性检查（强制）**：

```
1. 列出代码中所有 @PostMapping / @GetMapping / @PutMapping / @DeleteMapping
2. 对照 02-接口文档-内部.md 和 02-接口文档-外部.md
3. 出现"代码有文档无"或"文档有代码无" → 不通过，回 B4 补
4. 如 B4 双产物模式开启：额外检 Form/Vo 字段名/类型与 markdown 严格一致
```

### 段 2：CHANGELOG 段落生成

**自动汇聚 3 个数据源**：

| 数据源 | 提供内容 |
|---|---|
| `01-需求内容.md` 需求清单 | 一句话需求摘要 |
| `git log v{上一版本}..HEAD --oneline` | 实际 commit 列表 |
| B5 决策章 + B7 `qa/00-debug-log.md` | 涉及的设计变更与坑点修复 |

**输出格式骨架见独立模板文件** [`references/iter-summary.template.md` §模板 1](./references/iter-summary.template.md)，按 6 类标签（Added / Changed / Database / Fixed / Config / Removed）归类。

### 段 3：遗留 ⚠️ 沉淀

扫描以下文件中所有 `⚠️` 与 `❓`：

- `iterate/v{版本}/{业务模块}/01-需求内容.md`
- `iterate/v{版本}/{业务模块}/03-设计文档.md`
- `iterate/v{版本}/{业务模块}/qa/*.md`

每条标记按以下分类：

| 类型 | 处理 |
|---|---|
| 已澄清并落地 | 移除标记 |
| 已澄清但未落地（本版本不做） | 移到 `iterate/v{下版本}/{业务模块}/01-需求内容.md` 作为预定义需求 0 |
| 未澄清且未落地 | 同上 + 05-版本收尾.md 自反思段标"为什么没澄清就过去了" |
| 已观察到但暂时容忍（如性能可接受、历史数据兼容） | 写入 `05-版本收尾.md` §技术债清单 |

**强约束**：版本发布**绝不允许带 ❓** —— 必须全部分类处理掉。⚠️ 可以保留但需归类。

### 段 4：AI 自反思（retrospective.md）

**输出格式骨架见独立模板文件** [`references/iter-summary.template.md` §模板 2](./references/iter-summary.template.md)，含 5 节：本版本数据 / 踩过的坑 / 流程吐槽 / 下版本预防清单 / Skill 反馈。

**强约束**：第五节"Skill 反馈"是**通用 Skill 仓库的进化飞轮**——本节内容应单独提交一个 issue / PR 到 `agent-base-busi-flow` 仓库。

### 段 5：统一 git push

> B7 只 commit 不 push，避免半成品上 main。本段统一推送。

**push 前最后自检**（强制）：

| # | 检查 | 通过条件 |
|---|---|---|
| 1 | 集成测试是否全绿 | B8 第四道检查点已 OK |
| 2 | 完整性审计是否通过 | 段 1 表全 ✅ |
| 3 | CHANGELOG 是否已写 | `CHANGELOG-fragment.md` 已生成且追加到项目 CHANGELOG.md |
| 4 | ⚠️/❓ 是否全部分类处理 | 段 3 完成 |
| 5 | retrospective 是否已写 | 段 4 完成 |
| 6 | 待 push 的 commit 列表是否符合预期 | `git log origin/main..HEAD --oneline` 给用户看一遍 |
| 7 | 分支是否对（main / release/x / version/x）| 由 overlay 指定的版本分支策略 |

**主动告知文案**（最后一道人工审查检查点）：见 [`references/iter-summary.template.md` §模板 3](./references/iter-summary.template.md)。用户回 "推送" / "yes" 才执行 `git push`。**不自动 push**——这是版本发布的不可逆动作。

**push 后通知文案**：见 [`references/iter-summary.template.md` §模板 4](./references/iter-summary.template.md)。

---

## AI 反模式

1. **跳完整性审计** —— 直接生成 CHANGELOG → 漏需求 / 漏接口必现
2. **CHANGELOG 写技术语言** —— `feat(svc): refactor xxx interceptor` → 业务方看不懂，要翻译成业务语言
3. **CHANGELOG 写细节** —— 把字段映射 / SQL 全贴进去 → 应留在 `iterate/v{版本}/`
4. **❓ 带病发布** —— 让 ❓ 留在 01-需求内容.md 第六章就 push → 必有线上事故
5. **retrospective 写空话** —— "下次注意一点" / "继续努力" → 没沉淀价值，必须可执行（具体改哪个 overlay / 加哪条防呆）
6. **自动 push** —— push 是不可逆，必须用户显式确认
7. **跳 Skill 反馈** —— 不写第五节 → 通用 Skill 永远不会进化
8. **审计不通过硬过** —— 段 1 任一项 ❌ 直接进段 2 → 不合格，必须先回对应 Skill 补
9. **CHANGELOG 不挂 commit hash** —— 后续追溯不到具体改动
10. **📅 日期/作者凭印象写** —— 用 `git log` 真实数据，不要编

## 业务服务侧 overlay 必填

| 内容 | 用途 |
|---|---|
| 版本分支策略 | `main` 直推 / 走 `release/x` / 走 `version/x` PR 合并 |
| CHANGELOG 文件位置 | 项目根 / docs/ / 其他 |
| 上一版本 tag 名 | `v{上版本}` 还是 `release-{x}` 等 |
| 业务方读 CHANGELOG 的语言 | 中文 / 英文 / 双语 |
| 接口文档与代码一致性检测命令 | 项目专用脚本（如有）|
| 推送后通知机制 | webhook / 钉钉 / 飞书 / 邮件 |
