---
name: busi-coding-rules
description: "Java 编码通用基线：以《阿里巴巴 Java 开发手册》强制条款为基准，叠加 AI 编码通病防护。工具类选型 / 分层模式 / 字段命名等项目习惯由业务服务侧 overlay 指定，本 Skill 不锁死。"
---

# 通用编码基线

> **本 Skill 不锁死技术选型。** 工具类（Hutool / Apache Commons / Guava / 自研）、分层模式（3 层 / 4 层 / DDD）、字段命名、注解约定等都由**项目习惯**决定，写在业务服务侧 `.agent/coding-rules.md` 中，**优先级高于本 Skill**。
>
> 本 Skill 只管两类事：
> 1. **市面公认的通用基线** —— 引用《阿里巴巴 Java 开发手册》最新版【强制】条款
> 2. **AI 编码通病防护** —— 人类不太犯但 AI 经常犯的错

## 1. 基线引用：阿里巴巴 Java 开发手册

【强制】条款全部生效，重点关注（不限于）：

- 命名规范（类 / 方法 / 常量 / 包 / 数据库）
- POJO 规约（getter/setter、`equals`/`hashCode` 配对、boolean 字段不加 `is` 前缀）
- 集合陷阱（`Arrays.asList` 不可增删、`subList` 视图、`Collection.toArray(T[])` 用法）
- 并发处理（线程池禁用 `Executors`、用 `ThreadPoolExecutor` 显式构造）
- 日志规约（占位符 `{}`，禁止字符串拼接）
- 异常处理（不吞异常、`finally` 不 return、自定义异常携带上下文）
- MySQL（索引设计、字段类型、`SELECT *` 禁止）
- 工程结构、安全规约（SQL 注入、XSS、敏感信息脱敏）

【推荐】、【参考】条款由项目自行选择，**本 Skill 不强制**。

## 2. AI 编码通病防护

以下是 AI 经常犯、阿里手册不一定覆盖的错误，**所有项目都适用**：

### 2.1 不要为已有功能新建并行方法

新增方法前先搜索项目是否已有同名/相似方法。能复用则复用，**禁止两套逻辑各走各的**。
- ❌ 已有 `processOne()` 时新建 `processBatch()` 跑两套逻辑
- ✅ `processBatch()` 作为主实现，`processOne()` 委托 `processBatch(singletonList(x)).get(0)`

### 2.2 改动可追溯

diff 每一行都要能追溯到需求。**禁止**"顺手优化"相邻代码、重构没坏的东西、改无关注释/格式。

### 2.3 全限定类名禁令

代码体中禁止用 `com.xxx.yyy.ClassName` 形式声明字段或局部变量，统一在文件头 `import`。
- ❌ `private com.company.module.service.OrderService orderService;`
- ✅ `import com.company.module.service.OrderService;` / `private OrderService orderService;`
- 例外：两个同名类冲突时其一可用全限定名，**必须加注释说明冲突原因**。

### 2.4 循环内禁止远程调用

循环内禁止 DB / Feign / HTTP / Redis 调用。批量场景用 `IN` 查询、`mGet`、批量 RPC 接口。

### 2.5 统计聚合走 SQL，不要全量加载到内存

需要 COUNT/SUM 时直接 `COUNT/SUM + GROUP BY` 在 SQL 完成。不要把全量实体查到内存再 `stream().count()` / `Collectors.counting()`。前者传输几行聚合结果，后者加载全量到 JVM（可能上万行），性能差距数量级。

### 2.6 分页 total 不要硬编码 0

即使当前页 records 为空，total 仍可能非零（如请求超出实际页数）。硬编码 `0` 会导致前端分页组件错误。必须取真实分页结果的 `getTotal()`。

### 2.7 事务方法内禁止远程调用

`@Transactional` 方法内禁止 Feign / HTTP / RPC 调用。事务时间过长会拖死连接池，且远程调用失败时事务回滚语义不可控。

### 2.8 字符串拼接日志

日志用 `{}` 占位符，不用 `+` 拼接。即使生产日志级别关闭，拼接仍会执行 `toString` 浪费 CPU。
- ❌ `log.info("用户登录: " + userId);`
- ✅ `log.info("用户登录, userId={}", userId);`

### 2.9 魔法值

业务判断 / 赋值不用硬编码字面量，统一用枚举或常量类。**常量类归口位置由 overlay 指定**。
- ❌ `if (status == 1)` / `setType(0)` / `if ("APPROVED".equals(state))`
- ✅ 引用枚举或常量类（具体类位置见 `.agent/coding-rules.md`）

例外：日志/异常消息中的纯描述性字符串、数学常量（0/1/-1 用于索引/偏移）。

### 2.10 入参类型一致性

同一域对象的 ID 在所有接口中必须用同一种类型（`Long` 或 `String`），不允许 Controller A 用 `Long`、Controller B 用 `String`。

## 3. 业务服务侧 overlay 必须补充

以下项目特化内容由业务服务侧 `.agent/coding-rules.md` 提供，本通用 Skill **不预设默认值**：

| 内容 | 用途 |
|---|---|
| 工具类选型 | 判空、字符串处理、日期处理（Hutool / Apache Commons / Guava / JDK 原生 / 自研） |
| 项目分层模式 | 3 层（Controller/Service/Mapper）/ 4 层（含 DbService）/ DDD |
| BaseEntity 字段清单 + DDL 模板 | 审计字段、逻辑删除标志的字段名与值含义 |
| 常量类与枚举归口位置 | 第 2.9 条魔法值替代 |
| Bean 复制工具 | 项目内 `BeanUtils` / MapStruct / 手写 setter |
| 鉴权注解约定 | 前端接口 / 跨服务 Feign 分别用什么 |
| Feign / SDK 模块归口规则 | 跨模块通信走的共享库 |
| 服务暴露范围 | 哪些服务对外网、哪些只内网 |
| 接口路径前缀约定 | 是否重复 context-path |
| 日期格式与时区约定 | 序列化格式 / 时区 |
| 分页结果包装类 | `PageUtils<T>` / `IPage<T>` / 自定义 |
| ORM 框架与 Mapper 基类 | MyBatis-Plus / MyBatis / JPA / 项目自研基类 |
| 维度/权限/数据隔离查询规范（如有） | 项目特化 |

> overlay 完整范例参考 `kgd-doc/skills/xyk-coding-rules/SKILL.md`（XYK 项目实例）。

## 4. 冲突解决

当 overlay、阿里手册、本 Skill 三者出现冲突时：**项目 overlay > 阿里手册 > 本 Skill**。

原因：项目历史代码已成型，新代码必须保持风格一致；半红半绿的代码风格会让审查和维护成本翻倍。
