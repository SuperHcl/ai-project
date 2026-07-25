# 版本收尾模板（CHANGELOG / Retrospective / Push 文案）

> 本文件被 [busi-iter-summary/SKILL.md](../SKILL.md) 段 2 / 段 4 / 段 5 引用作为输出格式骨架。
> AI 在落地 `iterate/v{版本}/{业务模块}/05-版本收尾.md` 与 `CHANGELOG-fragment.md` 时，按本模板填充。

---

## 模板 1：CHANGELOG 段落（用于 CHANGELOG-fragment.md / 项目根 CHANGELOG.md）

```markdown
## [v{版本}] - {发布日期 YYYY-MM-DD}

### Added
- {需求 1 一句话} (#{commit hash 简写})
- {需求 2 一句话} (#{commit})

### Changed
- {既有功能调整} (#{commit})

### Database
- 新建表 `xxx` / 表 `yyy` 加字段 `zzz` (#{commit})

### Fixed
- {开发期发现的现存 bug 顺便修了} (#{commit})

### Config
- {新增配置项 / Nacos / 环境变量} (#{commit})

### Removed
- {下线了什么}（如果有）
```

**强约束**：
- 一句话摘要 = 业务读得懂的语言（不是 `feat(svc): impl xxx`）
- 每条挂 commit hash，便于追溯
- 内部实现细节（类名 / SQL / 字段映射）**不进 CHANGELOG**——细节在 `iterate/v{版本}/{业务模块}/` 里查

---

## 模板 2：retrospective（嵌在 05-版本收尾.md 的自反思段，5 节）

```markdown
# v{版本} 回顾

## 一、本版本数据

- 需求数：N
- 改动文件数：K
- 单测：A 个 / 集成测试：B 个 / 全绿
- 累计 commit：M 个
- 累计耗时：{开始日期} → {发布日期}（约 X 天）

## 二、踩过的坑（来自 develop/qa/00-debug-log.md）

| # | 症状 | 根因 | 教训 | 是否值得入下版本预防清单 |
|---|------|------|------|:---:|
| 1 | … | … | … | ✅ |

## 三、流程吐槽 / 改进建议

> AI 与人协作过程中本次发现的流程问题，下版本可以怎么改善。

- {例：B5 拷问太长，下次先发骨架让用户决定要不要详细}
- {例：B7 dev-loop 在 X 场景反复改 A 坏 B，systematic-debugging 触发太晚}

## 四、下版本预防清单

> 本版本独有的踩坑，要不要进 `busi-coding-rules` 业务侧 overlay？还是进 B6 §七防呆清单？

- [{级别}] {措施}（更新到 .agent/coding-rules.md / overlay-spec.md / 等）

## 五、Skill 反馈（写到 agent-base-busi-flow 仓库）

> 跑了一轮通用 Skill 后，发现哪些 Skill 描述需要修正？哪些边界不清？哪些反模式没覆盖到？

- {Skill 名}：{建议}
```

**强约束**：第五节"Skill 反馈"是**通用 Skill 仓库的进化飞轮**——本节内容应单独提交一个 issue / PR 到 `agent-base-busi-flow` 仓库。

---

## 模板 3：push 前主动告知文案（最后一道人工审查检查点）

```text
版本 v{版本} 已就绪（最后一道人工审查检查点）：

- 完整性审计：7/7 ✅
- 集成测试：全绿
- CHANGELOG：N 条已生成
- ⚠️ 遗留：A 条已沉淀到下版本，B 条进技术债，C 条容忍
- AI 反思：M 个坑已沉淀

待 push 的 commit：
  {hash} feat(...): ...
  {hash} test(...): ...
  ...

确认推送到 origin/{分支} 吗？
```

用户回 "推送" / "yes" 才执行 `git push`。**不自动 push**——这是版本发布的不可逆动作。

---

## 模板 4：push 后收尾文案

```text
已 push 到 origin/{分支}。版本 v{版本} 收尾完成 ✅

下一步建议：
- 如有 retrospective.md 第五节 Skill 反馈 → 提 issue 到 agent-base-busi-flow
- 通知运维 / DBA：DDL 见 03-设计文档.md §3.2
- 通知前端 / 测试：v{版本} 接口文档已就绪
```
