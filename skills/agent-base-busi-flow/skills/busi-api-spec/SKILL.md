---
name: busi-api-spec
description: "接口契约文档生成（8 步流程第 3 步）。从已澄清的需求内容中抽接口清单，Agent 自主读代码定位服务归属与调用链，不确定项一问一答补全。推荐双产物模式：B4-A markdown 接口文档（人审） + B4-B Form/VO/Controller 占位代码（机器同步 yapi/swagger 给前端）。"
next_skills: [busi-design-doc]
---

# 接口契约文档

## 定位

**8 步流程的第 3 步**，在第 2 步澄清完成后启动。本步骤的产出是**第一道人工审查检查点**的依据：接口签名稳定后，前端可以并行开发 mock，B7 编码阶段也以此签名为约束做 `mvn compile` 通过。

> **这里只产出"契约"，不产出"实现"**：方法签名、路径、入参出参字段、鉴权方式、错误码。业务逻辑只用一两句话概括，详细实现是 B5 设计文档 + B7 编码的事。

## 输入

- `iterate/v{版本}/{业务模块}/01-需求内容.md`（B3 澄清后的版本，第六章应已基本清空）
- 每个需求章节内的 §涉及接口表（接口名 / 改动类型 / 所属服务）
- 业务服务侧 `.agent/AGENT.md`（拿路径前缀规则、统一返回结构、错误码体系、鉴权注解约定）

## 输出

### 产物 A（必选）：markdown 接口文档

按归属同一模块平铺，用命名区分内部/外部（**不再分子目录**）：

```
iterate/v{版本}/{业务模块}/
├── 02-接口文档-内部.md   ← 前端 / PC / 移动端 HTTP 调用
└── 02-接口文档-外部.md   ← 跨服务 Feign / 对第三方暴露
```

仅需一者则只输出其中一个文件。

### 产物 B（推荐）：代码契约占位

在业务服务实际代码库中提前产出：

| 层 | 产出 | 状态 |
|---|---|---|
| `interfaces/.../{module}/Controller.java` | 接口类 + 方法签名 + Swagger 注解，方法体 `throw new UnsupportedOperationException("WIP - B7 实现");` | 编译过 |
| `接口参数 Form / Vo` | 字段 + Swagger `@ApiModelProperty` 描述 + 校验注解 | 编译过 |
| `Feign 客户端（如需）` | 接口 + 方法签名 | 编译过 |

**不产出**（留给 B7）：
- `application/` `domain/` `infrastructure/` 任何业务逻辑
- `Command` / `Dto` / `Entity` / `Repository`
- SQL / DDL / Mapper.xml
- Service 实现、Mapper 实现

**双产物价值**：B4-A 供设计评审 / 人类阅读；B4-B 通过 yapi/swagger 插件自动同步给前端，避免手工拷字段导致偏差。

### 产物一致性约束（强制）

- B4-A 和 B4-B 的字段名/类型/必填性/枚举取值 **必须完全一致**
- C1 检查点同时验两者，任一不一致立即驳回
C1 检查点主审清单：字段名一致 / 类型一致 / 必填性一致 / 枚举一致 / 鉴权一致 / 错误码一致

### 退路：单产物模式

项目未接入 yapi/swagger 同步插件 / B4 阶段不允许动代码 → 可仅产出 B4-A，在业务服务侧 `.agent/AGENT.md` 中明确声明「单产物模式」。

## 步骤

### Phase 1：提取接口清单

读 `01-需求内容.md`，从每个需求的 §涉及接口表汇总：

```
| # | 接口 | 改动类型 | 归属服务 | 调用方 |
|---|---|---|---|---|
| 1 | /xxx/list | 修改 | order-svc | 前端（内部） |
| 2 | InnerOrderApi.findByIds | 新增 | order-svc | inventory-svc（外部 Feign） |
```

**调用方**用于决定落到 `02-接口文档-内部.md` 还是 `02-接口文档-外部.md`。展示清单给用户**确认或补充**，等"OK"再继续。

### Phase 2：Agent 自主定位（先读代码，不要先问用户）

对每个接口，按以下顺序读代码，**能读出来的不要问**：

| 维度 | 工具 | 操作 |
|---|---|---|
| 服务归属 | `Grep` | 搜路径 `/xxx/list` → 找到 Controller → 记录服务名、Controller 全限定类名 |
| Controller 包路径 | `Grep` / `Glob` | 看现有同模块 Controller 的包归属 |
| 入参类 / 出参类 | `Grep` | 搜方法签名 → 找到 `Form` / `Vo` 类 → 列出现有字段 |
| 调用链下游 | `Grep` | 搜 Service 实现，记录调用了哪些 Feign / RPC / DB |
| 鉴权注解 | `Grep` | 看现有同模块接口用的鉴权注解（前端 / Feign 不同） |
| 现有字段类型 | `Grep` | VO 已有字段不要改类型，新增字段紧贴现有命名风格 |

**已存在的接口**：先把现有签名抄进文档，**仅标注本次的字段差异**（新增 / 修改 / 删除），不要全量重写，避免 diff 噪声。

**新增的接口**：参照同模块现有接口的命名/路径风格写新签名，不要创新。

### Phase 3：不确定项一问一答（复用 busi-req-clarify 节奏）

只对**读代码读不出来 + 需求文档没写**的项发问。每题用 `AskUserQuestion`，带推荐答案 + 影响面：

**常见提问维度**（仅对不确定项）：

1. **新增字段是否必填**？必填默认值什么？历史数据如何回填？
2. **枚举值域**——新增枚举的取值范围、命名风格（数字 vs 英文）
3. **接口分页 vs 全量**——返回数据量上限？需不需要分页？
4. **空值语义**——`null` / `""` / `0` 的业务含义
5. **鉴权范围**——前端接口 / Feign 内部 / 对外暴露三选一
6. **错误码**——业务错误用项目现有错误码 vs 新增？
7. **批量接口的最大批量数** —— 防止前端一把传 10w 条

**禁止**：替用户决定字段名 / 字段类型 / 返回结构。这些是契约，必须用户确认。

### Phase 4：落地

**产物 A（markdown）**：**必读** [`references/02-api-spec.template.md`](./references/02-api-spec.template.md) 作为输出格式骨架，按 §输出 路径写文件。

**产物 B（代码契约占位，推荐）**：

1. 在业务服务代码库按 §输出-产物B 清单生成 Controller / Form / Vo / Feign 接口
2. Controller 方法体统一写：
   ```java
   throw new UnsupportedOperationException("WIP - B7 实现");
   ```
3. Swagger 注解齐：`@Api` `@ApiOperation` `@ApiModel` `@ApiModelProperty(value="...", required=true)`
4. 校验注解齐：`@NotNull` `@NotBlank` `@Size` `@Valid`
5. 运行业务服务侧编译命令（从 `.agent/coding-rules.md` 取）验证 BUILD SUCCESS
6. 提交为独立 commit，便于 B7 交接时 diff 清晰

写完后**简要汇报**：
- 内部接口 N 个 / 外部接口 M 个
- 新增 X / 修改 Y / 删除 Z
- 关键决策 K 条（已写入对应接口的"业务逻辑"段）
- 代码契约占位编译状态：✅ BUILD SUCCESS / ⏸ 单产物模式未开启

最后**主动提示**："是否进入 `busi-design-doc` 输出人类可读设计文档？"（不自动跳转）。

## 文档模板

**输出格式骨架见独立模板文件**：[`references/02-api-spec.template.md`](./references/02-api-spec.template.md)

模板含：内部接口文档（接口概述 / 接口列表 / 请求参数 / 响应结构 / 响应字段 / 业务逻辑摘要 / 调用链路 / 错误码）+ 外部接口（Feign）的额外标注。落地时**必须读取该模板作为输出骨架**，不能凭记忆拼。

## AI 反模式（这步最常犯）

1. **凭空编路径** —— 没读代码就写 `/xxx/list`，要先 `Grep` 看现有同模块路径风格
2. **凭空编字段类型** —— 不读现有 VO 就写 `Long id`，已有字段用 `String` 你写 `Long` 就崩了
3. **出参敷衍** —— 写 `data: Object`、`data: 见接口返回` 等价于没写。每个字段都要列。
4. **漏鉴权 / 错误码** —— AI 经常只写 happy path，鉴权和错误码必须显式写出
5. **修改类接口写成全量重写** —— 已有接口只写**差异**（哪个字段新增 / 类型改了 / 必填变可选），不要把整张表抄一遍
6. **批量接口不写上限** —— "传一个 List" 没说上限 → 前端一把传 10w 条 → 雪崩。必须明确批量数上限
7. **跨服务调用不标 Feign** —— 前端调内部接口 vs Feign 内部调用，鉴权和错误处理不同，必须标清楚

## 业务服务侧 overlay 必填

| 内容 | 用途 |
|---|---|
| 接口路径前缀规则 | `/{module}/{layer}/v{版本}/{action}` 还是其他风格 |
| 统一返回结构 | `Result<T>` / `R<T>` / 自定义 |
| 错误码体系 | 错误码段位划分（如 4xxxx 客户端 / 5xxxx 服务端） |
| 鉴权注解清单 | 前端登录 / Feign 内部 / 对外公开 各用什么注解 |
| Feign 模块归口 | Feign 接口类放哪个模块、命名规则 |
| 分页结构 | `IPage<T>` / `PageUtils<T>` / 自定义 |
| 时间字段格式 | `yyyy-MM-dd HH:mm:ss` / 时间戳 / ISO 8601 |
| **B4 产物模式** | 双产物（推荐） / 单产物（退路） |
| **yapi/swagger 同步插件** | 插件名与触发命令 |
| **Controller 占位实现默认写法** | `throw new UnsupportedOperationException("WIP - B7 实现")` 还是项目自定义 |
