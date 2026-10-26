# 域地图与边界断言模板

## 一、域地图（填完不超过 1 页）

```
域：<名称>                     负责人：<角色>
─────────────────────────────────────────────
不变量（永远为真）
  1. <例：一张采购单只属于一个供应商>
  2. <例：审批中的单据不可改金额>

边界（禁止被域外引用）
  - <类/包列表>

变化速率分组（一起变的分在同包，不一起变的分开）
  - 高频：<接口契约、表单校验>
  - 低频：<数据模型、存储结构>

依赖方向
  本域可以依赖：<列表>
  禁止依赖：<列表>
  允许被谁依赖：<列表>
```

## 二、判定归属（权限/鉴权类改动必填）

所有"谁能对什么做什么"的判断，收敛成四元组，判定只在一处发生：

| 概念 | 含义 | 落在哪 |
|---|---|---|
| Principal | 主体：员工 / 合作伙伴 / 系统 | 统一主体包 |
| Action | 动作：权限码 / 操作码 | 菜单与权限码表 |
| Resource | 资源：对象类型 + id | 各域提供"资源解析" |
| Scope | 范围：组织 / 公司 / 国家 / 供应商 / 本人 | 统一范围服务 |
| Decision | 结论：allow / deny + 理由 | **唯一决策入口** |

铁律：

- 判定只允许出现在 `pep`（拦截/注解桥接）层；业务 service **禁止**直接读当前用户
- 域内只允许声明策略，不允许自己实现判定流程
- "只校验登录"的旁路必须登记在白名单文件里，并由测试断言条目数不增长

## 三、ArchUnit 断言模板

老仓库直接全量断言会全线失败，团队会绕过。正确做法是**冻结现状**，只拦新增违规：

```java
@AnalyzeClasses(packages = "com.example.srm",
                importOptions = ImportOption.DoNotIncludeTests.class)
class DomainBoundaryTest {

    // 1. 判定只能在 pep 层读当前用户（存量用 FreezingArchRule 冻结，只拦新增）
    @ArchTest
    static final ArchRule 判定只在pep层 =
        FreezingArchRule.freeze(
            noClasses().that().resideOutsideOfPackage("..security.pep..")
                .should().dependOnClassesThat()
                .haveFullyQualifiedName("cn.dev33.satoken.stp.StpUtil"));

    // 2. 域之间禁止互引（逐个域配置）
    @ArchTest
    static final ArchRule 权限域不被业务域反向依赖 =
        FreezingArchRule.freeze(
            noClasses().that().resideOutsideOfPackage("..security..")
                .should().dependOnClassesThat().resideInAPackage("..security.pdp.."));

    // 3. 域之间无环
    @ArchTest
    static final ArchRule 域之间无循环依赖 =
        slices().matching("com.example.srm.(*)..").should().beFreeOfCycles();

    // 4. 附件访问策略必须实现统一接口（防止再写第 N 份）
    @ArchTest
    static final ArchRule 附件策略必须实现统一契约 =
        classes().that().haveSimpleNameEndingWith("AttachmentAccessPolicy")
            .and().resideOutsideOfPackage("..security.policy..")
            .should().beAssignableTo(ResourceAccessPolicy.class);
}
```

要点：

- `FreezingArchRule` 会在首次运行时把现存违规冻结到 `archunit_store/`，之后**只对新违规失败**。这是老系统唯一能落地的用法。
- 断言要少而硬（3–5 条）。写 30 条没人维护，最后会被整体注释掉。
- 每条断言对应域地图里的一条依赖方向，不要写没有文档依据的断言。

## 四、迁移四阶段（不重写）

| 阶段 | 动作 | 可独立交付 |
|---|---|---|
| 1 | 合并概念（枚举、主体、范围定义），只加适配不改行为 | 是 |
| 2 | 引入单一决策入口，内部仍调旧实现 | 是 |
| 3 | 抽组合子，把散落实现收敛为声明式 | 是 |
| 4 | 上断言锁边界，然后删旧代码 | 是 |

任何一步要求"全部改完才能运行"就是方案错了。

## 五、参考实例（SRM 权限域，2026-10 现状）

诊断数据（可作为同类问题的判据）：

- `base/permission` 单包 **51 个类**，混了四种变化速率：技术设施、域策略、数据范围、菜单写入
- "附件谁能看"实现 **约 20 次**，散在 5 个包
- 授权模型 **4 套并存**：`Sys*` / `Portal*` / `CommonPermission*`（单个 impl 71KB）/ `SupplierPermission*`（独立 4 张表）
- 判定入口 **3 处**：303 个文件的 `@PreAuthorize`、service 内手判、workflow 自成一套 `WorkflowAccess`
- 反证：Registry 模式在 3 处各收敛一次——抽象方向是对的，只是没收敛成一次

目标结构：

```
security/
├── model/    Principal, Action, Resource, Scope, Decision
├── policy/   Predicate 组合子：sameOrg() participant() roleIn() supplierBound() selfOnly() …
├── pdp/      PermissionDecider —— 唯一决策入口
├── pep/      统一拦截器 + 注解桥接
└── store/    适配现有 4 套表，不重写
```

域内策略从 5–9KB 的类降为 10 行声明。**先合并概念，再收策略，最后删旧实现。**
