# agent-arch-guard（**ArchGuard**）

> 治三种病：**AI 过度设计**、**方案与文档看不懂**、**review 越来越吃力**。
> 仓库名 `agent-arch-guard` 是物理标识，沟通统一用别名 **ArchGuard**。

## 它解决什么问题

规范写进 `AGENTS.md` 之后，问题并没有消失——因为 AGENTS 只能在会话开始注入一次，是**声明**：不可验证、遵守率随长度衰减、违规零成本。

ArchGuard 补的是 AGENTS 做不到的三件事：

| 能力 | 文档 | 本插件 |
|---|---|---|
| 时序 | 只在开始时 | 方案前 / 命中敏感路径 / 交付前分别介入 |
| 加载 | 全量 | 命中关键词才加载对应 SKILL |
| 执行 | 零成本违规 | `verify.py` 不过不放行，Git hook 强制 |

## 两条主流程 + 四个判断 Skill

**新需求** → `archg-feature`：验收口径 → 范围预算 → 落位检查 → 交付契约（四道门，不重复项目已有的设计流程）

**旧代码 review/改造** → `archg-legacy`：`audit.py` 选点 → 定目标形态 → 单单元改造 → 分级 review

| Skill | 触发场景 | 产出 |
|---|---|---|
| `archg-feature` | 新需求 / 新接口 / 加功能 | 验收口径 + 范围预算 + 交付四项 |
| `archg-legacy` | review 旧代码 / 改造 / 接手看不懂的模块 | 改造选点 + 三档 review 方法 |
| `archg-plan` | 要给方案 / 重构 / 跨域改动 | ADR-lite（≤1 页）+ review 导航 |
| `archg-budget` | 过度设计 / 测试太多没用 / 要不要抽接口 | 抽象预算 + 测试预算 |
| `archg-boundary` | 架构、分层、包结构、权限鉴权域改动 | 域地图 + 依赖方向 + ArchUnit 断言 |
| `archg-ratchet` | 老项目、god class、往巨型类加功能 | 只许变小的基线门禁 |

## 五个可执行物（不靠自觉）

```
scripts/scope_check.py 范围预算：文件数/新增行/新增端点/新增表（新需求用，可阻断）
scripts/audit.py       旧代码体检：按「复杂度 x 变更热度」排改造候选（旧代码用）
scripts/ratchet.py     已知超大文件只许变小；新文件超上限即阻断
scripts/scan_design.py 单实现抽象 / 超大文件 / 同类概念散落（候选清单）
scripts/verify.py      统一入口，依次跑棘轮 + 范围预算 + 扫描
```

三者都是纯标准库 Python，无第三方依赖，跨平台。**这是唯一与 harness 无关的强制层**——Git hook 不关心你用哪个 AI。

## 三 harness 支持

| 能力 | Qoder | DSH | Codex |
|---|---|---|---|
| Skill 自动发现 | `.qoder/skills/` | `.dsh/skills/` | 无原生，摊平为 `.codex/prompts/*.md` |
| 常驻规则 | `.qoder/rules/arch-guard.md` | `AGENTS.md` 标记块 | `AGENTS.md` 标记块 |
| 可执行门禁 | git pre-commit | git pre-commit | git pre-commit |
| 用户级安装 | 不支持（项目级） | `~/.dsh/skills/` | `~/.codex/prompts/` |

> Codex 没有原生 Skill 机制，因此 SKILL 被摊平成斜杠 prompt；判定内容与另两者完全一致，只是触发方式不同。

## 快速开始

```powershell
# 装到目标项目（自动探测 .qoder / .dsh / .codex）
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Project d:\workspaces\ai\srm -Harness all

# 先看会改什么
.\install.ps1 -Project . -Harness all -DryRun

# 跨平台直接调 Python
python -I scripts/install.py --project . --harness all
```

安装后：

```bash
python -I .arch-guard/ratchet.py --init    # 记录现状基线（只记录不判失败）
python -I .arch-guard/verify.py            # 交付前自检
```

详见 [INSTALL.md](./INSTALL.md)。

## 目录

```
agent-arch-guard/
├── rules/AGENT.md                     常驻硬约束（注入 AGENTS.md / .qoder/rules）
├── skills/archg-*/SKILL.md            6 个按需加载的判断 Skill
│   ├── archg-plan/references/adr-lite.md
│   ├── archg-feature/references/acceptance.md
│   ├── archg-legacy/references/review-method.md
│   └── archg-boundary/references/domain-map.md
├── scripts/                           安装器 + 三个可执行检查
```

## 设计原则

- **上下文稀缺** — SKILL 只写 AI 无法从代码推断的东西；能从仓库读到的绝不复制进文档
- **可判定优先** — 能写成断言的规则不进文档；进文档的必须是无法自动判定的判断
- **比例式门禁** — 老仓库用基线冻结现状，只拦新增；全量断言会让团队整体绕过
- **不重复造轮子** — 与项目内已有 `.agent/`、BizFlow-8 等 overlay 共存，只补"判断与门禁"，不接管流程

## 与其它插件的关系

- 与 `agent-base-busi-flow`（BizFlow-8）互补：BizFlow-8 管**流程步骤**，ArchGuard 管**设计判断与腐烂门禁**。
- 与项目自带 `.agent/rules` 不冲突：ArchGuard 的常驻块只占 AGENTS.md 中一对标记行之间的区域，块外一律不改。
