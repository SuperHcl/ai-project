---
name: srm-feature
description: Use when 在 SRM 里接新需求、新增接口/模块/字段/表，或给现有功能加分支。用于把需求压到可评审、可验收的范围；纯 bug 修复、纯配置改动不适用。
---

# SRM 新需求

规则真源在项目 `.agent/`（coding-rule / db-rule / naming-registry / java-conventions）。**本 Skill 不复制那些规则**，只补四件 `.agent/` 不管的事。

## 1. 先写验收口径（不写不设计）

在 `.archguard/spec/<需求简称>.md` 写一页，模板见 [验收口径](./references/acceptance.md)：谁用、什么数据、成功长什么样、失败怎么办、怎么验、谁签字。

判据：**写不出"失败时用户看到什么"，说明还没想清楚。**

禁止用单元测试代替它。SRM 现在有 1300+ 测试类，它们证明的是代码按 AI 的假设运行，不证明业务要的是这个。

## 2. 范围预算

```bash
python -I .archguard/devguard.py check
```

超限时的处理顺序是**砍需求**，不是改 `.archguard/policy.json`。确实要改预算，写一句理由并让人确认。

经验值：一次能评审完的上限约 400 行生产代码 / 5 个端点 / 2 张表。

## 3. 落位四问（写代码前回答）

| 问题 | SRM 里的答案长什么样 |
|---|---|
| 放哪个包？ | 业务域在 `base/` 或既有域包下；Controller 只能落 `controller/{pc,app}/{staff,partner}` 或 `internal/common/shared` |
| 照哪个范本？ | 指得出一个现有的、同类业务的类。指不出 → 先说清为什么不复用 |
| 要新增抽象吗？ | 要 → 先给三行证明：现有实现数 / 第二个实现的具体触发条件 / 内联代价 |
| 动不动巨型类？ | 动 → 先把本次要改的方法切出去，再在新类里改。**不许往 2000 行的类里加逻辑** |

进一步约束：

- `common` / `feign` 必须 Java 8 字节码：禁用 `List.of`、`record`、`var`、文本块、`@Serial`
- Entity 不出 `base` 包；出参用 Vo，入参用 Form，对外用 feign DTO
- `third/` 下的参数类不与业务 Form/Vo 混用
- 新增 `@FeignClient` 必须显式 `contextId`，且路径与 `controller/internal` 同步

## 4. 交付四项（先导航后结论）

1. **差异**：改了哪些文件、每个为什么
2. **证据**：`devguard.py check` 输出 + 实际跑过的命令
3. **review 导航**：先看哪三处、哪些是样板可跳过
4. **不确定性清单**：哪几处是猜的、简化了什么、哪些没验证

`check` 未通过不得说"完成"。

## 反模式

- 一次做"完整版"，把第一版做成终版
- 顺手加字段/表/接口，理由是"以后要用"
- 用测试数量代替验收口径
- 把新逻辑塞进既有巨型类
- 夹带"顺手优化"，和本次需求无关

## 完成条件

验收口径已写且人确认；`check` 通过；落位四问有答案；交付四项齐全。
