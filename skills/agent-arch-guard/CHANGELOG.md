# CHANGELOG

## v0.2.0 — 2026-10-26

补齐两条主流程：新需求、旧代码 review 改造。

### 新增

- `skills/archg-feature` — 新需求四道门：验收口径 → 范围预算 → 落位检查 → 交付契约；附 `references/acceptance.md` 验收口径模板
  - 只加项目既有流程没有的门，不重复 BizFlow-8 等既有步骤
  - 明确禁止用单元测试代替验收口径（AI 验证 AI 的假设是该项目的真实风险）
- `skills/archg-legacy` — 旧代码 review 与改造：audit 选点 → 定目标形态 → 单单元改造 → 三档 review；附 `references/review-method.md`
  - 三档：L1 扫签名（判职责）/ L2 审四类风险（状态归属、事务边界、异常吞没、并发幂等）/ L3 只逐行读改动窗口
  - 改造单元 DoD 含"目标文件必须变小"，仅重排不算改造
- `scripts/scope_check.py` — 范围预算：文件数 / 新增行 / 新增端点 / 新增表，超限返回 1
- `scripts/audit.py` — 旧代码体检：按「复杂度 × 变更热度」排改造候选，并给可执行改造方向
- `.arch-guard/budget.json` — 安装时生成默认预算（不覆盖项目已调整的值）
- `verify.py` 改为三段：棘轮（阻断）+ 范围预算（默认只报告，`--scope-strict` 阻断）+ 设计扫描

### 设计取舍

- **范围预算默认不阻断**：直接卡死会让维护性提交也被拦，团队会整体绕过；先报告，稳定后再开 `--scope-strict`。
- **audit 只排「又大又还在动」的**：又大但不动的重构收益最低、风险最高，明确建议暂缓。
- **特征测试定位为行为基线**，不是覆盖率工具；改造后不得删除。

## v0.1.0 — 2026-10-26

首个可用版本。目标是治三件事：AI 过度设计、方案与文档看不懂、review 吃力。

### 新增

- `rules/AGENT.md` — 5 条常驻硬约束：方案先行、抽象预算、测试预算、边界与判定归属、交付契约
- `skills/archg-plan` — ADR-lite 方案闸 + review 导航 + 不确定性清单
- `skills/archg-budget` — 抽象预算与测试预算（配额 + 三行证明）
- `skills/archg-boundary` — 域地图、依赖方向、ArchUnit 断言模板（含 SRM 权限域实例）
- `skills/archg-ratchet` — 腐烂棘轮：已知超大文件只许变小
- `scripts/ratchet.py` — 基线校验，支持 `--init / --check / --update / --force-raise`
- `scripts/scan_design.py` — 单实现抽象、超大文件、同类概念散落的候选扫描
- `scripts/verify.py` — 统一校验入口（棘轮阻断 + 扫描只报告）
- `scripts/install.py` + `scripts/install.ps1` — 三 harness 安装器（Qoder / DSH / Codex），幂等、可 dry-run、带自检
- Git pre-commit 集成（可选，与已有 hook 冲突时拒绝覆盖）

### 设计取舍

- **判定优先于文档**：能写成断言的规则不进 SKILL；进 SKILL 的必须是无法自动化的判断。
- **基线而非全量**：老仓库直接上全量断言会全线失败并导致团队绕过，故用基线冻结现状、只拦新增。
- **Codex 无原生 Skill**：摊平为 `.codex/prompts/*.md`，并在 README 中如实标注差异，不假装等价。
- **可执行层与 harness 解耦**：Git hook 是唯一跨工具生效的强制点，三个 harness 共用同一份检查器。

### 已知限制

- `scan_design.py` 用正则判断接口/实现关系，不解析完整语法树；结论是候选，需人工复核。
- Qoder 仅支持项目级安装。
- Codex 的项目级 prompt 支持取决于版本；若斜杠命令不可见，用 `--user-level` 重装。
