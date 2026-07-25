---
name: busi-project-init
description: "项目 overlay 初始化（前置 Skill，不属于 8 步流程）。检测目标项目 .agent/ 下 3 个 overlay 文件是否就绪，缺失则按模板生成骨架并引导用户填充项目特化内容。安装后首次使用或新项目接入时触发。"
next_skills: [busi-flow-orchestrator]
---

# 项目 overlay 初始化

## 定位

**前置 Skill，不属于 B2-B9 流程链。** 在 `install.ps1` 安装 skills 之后、用户开始第一个版本开发之前执行。

解决一个痛点：`install.ps1` 只把 `skills/busi-*/` 复制到 `.qoder/skills/`，但 10 个 skill 依赖 `.agent/` 下的 3 个 overlay 文件才能正常工作。目前缺失仅告警不阻断，导致用户开始 B2 后 skill 找不到项目特化约束，产出质量下降。

本 Skill 负责：
1. **检测** `.agent/` 下 3 个 overlay 文件是否存在
2. **生成** 缺失文件的骨架模板（带 TODO 标记）
3. **引导** 用户填充关键项目信息（包路径、模块结构、技术栈等）

> ⚠️ 本 Skill 不启动 B2-B9 流程。完成后提示用户说"开始 v{X} 开发"进入 `busi-flow-orchestrator`。

## 触发词

| 触发词 | 行为 |
|---|---|
| "初始化项目" / "init project" / "初始化 overlay" | 检测 + 生成缺失的 overlay 文件 |
| "检查 overlay" / "overlay 状态" | 仅检测，报告缺失项，不生成 |

## 3 个 overlay 文件职责

| 文件 | 职责 | 消费方 |
|---|---|---|
| `.agent/AGENT.md` | 项目骨架硬约束：模块边界、包路径前缀、接口路径前缀、文档落地位置、终端约束、不变量 | 所有 Skill 共享，BizFlow-8 通用规则的项目级覆盖 |
| `.agent/coding-rules.md` | 编码 overlay：工具选型、分层模式、BaseEntity 字段、常量归口、Bean 拷贝、鉴权、Feign 归口等 | `busi-coding-rules` 的项目级覆盖，优先级最高 |
| `.agent/overlay-spec.md` | B2-B9 流程步骤的项目特化补充：iterate 根目录、文档分层、版本号规则、测试框架等 | `busi-flow-orchestrator` + 各 B{N} Skill |

## 步骤

### 步骤 1：检测现有 overlay

读取目标项目根目录下 `.agent/` 的文件清单：

```
.agent/
├── AGENT.md          ← 项目骨架
├── coding-rules.md   ← 编码 overlay
└── overlay-spec.md   ← 流程 overlay
```

检测结果分 4 种：

| 情况 | 处理 |
|---|---|
| `.agent/` 目录不存在 | 全部 3 个文件缺失 → 步骤 2 全量生成 |
| 目录存在但 3 个文件全缺 | 同上 |
| 部分缺失 | 只生成缺失的文件，保留已有文件不动 |
| 3 个文件全存在 | 报告"overlay 已就绪"，退出 |

## 步骤 2：深度探测项目信息

生成模板前，**必须先读取项目实际代码**，尽量预填而非全留 TODO。模板中标注「由 busi-project-init 探测后填写」的章节，必须通过代码扫描获取真实信息。

**AGENT.md §B（项目骨架硬约束）和 coding-rules.md 的核心内容，必须从代码中推断，不得预设固定结构。**

| 探测项 | 方法 | 预填到 |
|---|---|---|
| 项目类型 | 查 `pom.xml`（Maven）/ `build.gradle`（Gradle）/ `package.json`（前端） | AGENT.md 标题 |
| 模块结构 | 解析 `pom.xml` 的 `<modules>` 或子目录 `pom.xml`，读取每个模块的实际包结构 | AGENT.md §B.1 |
| 包路径前缀 | 扫描 `src/main/java/` 下的实际包路径 | AGENT.md §B.2 |
| 分层模式 | 扫描包结构（如 controller/service/mapper 三层 / interfaces/application/domain DDD 风格 / 其他） | coding-rules.md §2 |
| 接口路径前缀 | 扫描已有 Controller 的 `@RequestMapping` / `@GetMapping` 等注解 | AGENT.md §B.3 |
| 技术栈版本 | `pom.xml` 的 parent / Spring Boot version / Java version | AGENT.md §F 不变量 |
| 依赖库清单 | 扫描 `pom.xml` / `build.gradle` 的依赖（工具类库、ORM 框架、Bean 拷贝工具等） | coding-rules.md §1/§5/§12 |
| 已有基类 | 搜索项目中是否有 BaseEntity / 审计字段自动填充 | coding-rules.md §3 |
| 异常体系 | 搜索项目中已有的 Exception 类 / 全局异常处理器 | coding-rules.md §14 |
| 分页实现 | 搜索 PageQuery / PageResult / IPage 等分页相关类 | coding-rules.md §11 |
| 测试框架 | 查 `src/test/` 下已有测试的 import（JUnit4/5, Karate, RestAssured） | overlay-spec.md B8 |
| Service 模式 | 扫描已有 Service 是否为 interface + Impl 双层 | coding-rules.md §16 |
| 对象传递链路 | 搜索 VO / DTO / Form / Command 等对象类型 | coding-rules.md §18 |

> 探测结果列出给用户确认，**不擅自写入文件**。用户确认后才填入模板。
> **不同项目结构千差万别**——不要预设"必有 common/feign/server"或"必有 DDD 分层"。以代码实际结构为准。

### 步骤 3：交互式收集关键信息

对探测不到的关键信息，**逐项提问**（每项给推荐答案）：

**必问清单**（无法从代码探测的）：

1. **项目名称**（如 `OCS` = 海外海关系统）
2. **业务领域简述**（一句话，如"蜜雪冰城海外报关业务"）
3. **iterate 根目录**（如 `doc/ai-doc/iterate/` / `iterate/`）
4. **版本号格式**（如 `v{major}.{minor}.{patch}` / `release-{x}`）
5. **数据库表前缀**（如 `ocs_` / `t_` / 无前缀）
6. **接口路径前缀模式**（如 `/admin/{bc}/{action}`）
7. **commit message 语言偏好**（中文 / 英文）

**条件提问**（探测到特定结构时追问）：

8. 如是 Maven 多模块 → 各模块职责边界（哪个模块放 Form/VO，哪个放 Feign Client）
9. 如检测到 MyBatis-Plus → 是否用 `@TableLogic` 逻辑删除 + BaseEntity 审计字段
10. 如检测到 MapStruct → Bean 拷贝工具确认为 MapStruct

### 步骤 4：生成缺失文件

读取对应模板文件作为**章节骨架参考**，基于探测结果和用户确认值生成最终内容，写入目标项目：

- **AGENT.md** → 参考 [`references/AGENT.md.template`](./references/AGENT.md.template) 的章节结构 → 填入从代码探测到的真实内容 → 写入 `<项目>/.agent/AGENT.md`
- **coding-rules.md** → 参考 [`references/coding-rules.md.template`](./references/coding-rules.md.template) 的章节结构 → 填入从代码探测到的真实内容 → 写入 `<项目>/.agent/coding-rules.md`
- **overlay-spec.md** → 参考 [`references/overlay-spec.md.template`](./references/overlay-spec.md.template) 的章节结构 → 填入用户确认值 → 写入 `<项目>/.agent/overlay-spec.md`

**生成规则**：
- 探测到 + 用户确认的值直接写入，不留 TODO
- 探测不到且用户跳过的值，留 `<!-- TODO: {说明} -->` 标记
- 文件头加生成时间戳和"由 busi-project-init 生成"注释
- 已存在的文件**不覆盖**（即使内容为空也不动）
- **§B 模块边界和 coding-rules 核心内容必须反映项目真实结构**——如果项目是单模块、没有 Feign、不用 DDD，就不要生成这些不存在的内容

### 步骤 5：生成报告

输出初始化报告：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 项目 overlay 初始化完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 已生成：
  - .agent/AGENT.md         (项目骨架，{已填项数}/{总项数} 项已填充)
  - .agent/coding-rules.md  (编码 overlay，{已填项数}/{总项数} 项已填充)
  - .agent/overlay-spec.md  (流程 overlay，{已填项数}/{总项数} 项已填充)

⚠️ 待人工补充的 TODO 项：
  - .agent/AGENT.md
    - §B.3 鉴权策略（待首个接口确定后回填）
    - §F 不变量中的版本兼容性约束
  - .agent/coding-rules.md
    - §6 鉴权注解（待 sample 完整后补充）
    - §15 错误码段位规划

📋 后续操作：
  1. 打开上述文件，搜索 <!-- TODO --> 逐项填充
  2. 鉴权相关项可在首个需求（B4 接口设计）时回填
  3. 填充完成后说"开始 v{X} 开发"进入 8 步流程

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 与 install.ps1 的配合

`install.ps1` 安装完 skills 后会检测 `.agent/` overlay 状态：

- **全部存在**：正常输出 trigger map
- **部分/全部缺失**：打印醒目提醒块，建议用户在 Qoder 中说"初始化项目"触发本 Skill
- **`-InitOverlay` 参数**：install.ps1 直接从模板目录复制骨架文件到目标项目（非交互式，全 TODO 标记，适合 CI 场景）

## AI 反模式

1. **覆盖已有 overlay** —— 已存在的 `.agent/` 文件绝不覆盖，即使内容看起来不完整
2. **跳过探测直接生成全 TODO** —— 能从代码探测的信息（包路径、模块结构、技术栈版本）必须先探测再问，不要全留 TODO 增加用户填写负担
3. **不确认就写入** —— 探测结果必须列出给用户确认，不擅自写入
4. **生成后不报告** —— 必须输出初始化报告，列明已填项和待人工补充的 TODO 项
5. **越界启动 B2-B9** —— 本 Skill 只初始化 overlay，不启动开发流程。完成后提示用户说"开始 v{X}"进入 orchestrator
6. **生成过于详细的模板** —— 模板是骨架不是百科全书，每节给一两句说明 + TODO 标记即可，详细约束由用户按需补充
