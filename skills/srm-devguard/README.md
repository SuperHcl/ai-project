# srm-devguard（**DevGuard**）

> 只解 SRM 的两个问题：**新需求做歪**、**旧代码看不懂**。
> 不做流程编排，不产编号文档，不要求任何人改变现有协作方式。

## 三个动作

```bash
# 新需求 / 改动交付前：只报本次新增的问题
python -I .archguard/devguard.py check

# 旧代码从哪开始看：按「复杂度 x 变更热度」排候选
python -I .archguard/devguard.py audit --top 15
python -I .archguard/devguard.py audit --file SysUserServiceImpl

# 设计文档机械预检（不代替人工评审）
python -I .archguard/devguard.py review --doc docs/xxx-design.md --code . --roles CGY,CGZZ
```

一条命令一个动作，没有状态机、没有步骤编号、没有"第 N 道卡口"。

### review 能判什么、不能判什么

| 能（机械） | 不能（必须人工） |
|---|---|
| 必备图是否齐（sequence / flowchart / ER） | 图里的方案对不对 |
| 测试矩阵是否存在（表头含 测试对象/必测场景/用例） | 用例是否覆盖真实风险 |
| 角色码是否都在文档里出现 | 权限语义是否正确（并集/交集/拒绝） |
| 完整 SQL 的去重表数是否超限 | SQL 语义与执行计划 |
| 正文引用的类名、`类.方法` 在代码里是否存在 | 缓存一致性与撤权时效是否可接受 |
| 文档是否把"拟新增"标清楚 | 迁移顺序是否可执行 |

判定口径刻意保守：图里的名字不参与代码核对（那是设计节点），已标"新增"的类不做事实核对，
提示词只报未被否定的写法（文档写"禁止内存分页"不算违规）。

## 刻意不做的（以及为什么）

| 不做 | 理由 |
|---|---|
| 流程状态机（`.flow-state.json` 那类） | 它是为多头并行协作设计的；单人 + Agent 下维护状态本身比状态更有成本 |
| 8 步 / 5 道卡口 | 卡口要人签字。一个人自审 5 次是形式主义，审查质量反而下降 |
| 编号产物文档（`01-` `02-` `03-`） | 文档数量不产生决策，只产生 review 负担 |
| 全量报错 | 5019 个文件里存量问题一片，全量报等于没人看 |
| 新建文档目录 | 项目 AGENTS.md 明确禁止；本工具产物全部落在 `.archguard/` 并自动加入 `.git/info/exclude` |

唯一保留的一条外部做法：**卡口必须落在具体产物上**——所以新需求必须留下"验收口径"这一页，其余都可以口头。

## 检查项（都只报「新增」）

存量问题在 `init` 时冻结，之后只报新增，所以第一次跑不会被 5000 个旧问题淹掉。

| 检查 | 判据 |
|---|---|
| `flowable-import` | `srm-server` 禁止 `import org.flowable.*` |
| `jdk9-api` | `common`/`feign` 禁用 `List.of` / `record` / `var` / 文本块 / `@Serial`（Java 8 字节码） |
| `entity-leak` | Entity 不得被 `base` 之外的包引用 |
| `controller-layout` | Controller 必须落 `controller/{pc,app}/{staff,partner}` 或 `internal/common/shared` |
| `feign-context-id` | `@FeignClient` 必须显式 `contextId` |
| `third-form-mixing` | `third/` 参数类不得引用业务 Form/Vo |
| 超大文件棘轮 | 基线内文件只许变小；新文件超 600 行即阻断 |
| 范围预算 | 文件数 / 新增行 / 新增端点 / 新增表 |
| 测试气味 | 新增测试里出现 `verify(协作者)` 或 `@Disabled` |

阈值全在 `.archguard/policy.json`，**调参不用改代码**。

## 安装

```powershell
# 1) 装到本地（会创建 .archguard/ 并自动排除，不污染仓库）
python -I <插件目录>\runner\devguard.py install --root d:\workspaces\ai\deepseek\srm --harness qoder

# 2) 冻结现状（只做一次；以后收敛了就重跑 init 收紧）
python -I .archguard\devguard.py init

# 3) 自检
python -I .archguard\devguard.py check
```

`--harness` 决定 skill 落到哪里（不装 skill 也能用 runner，只是 IDE 里不会自动触发）：

| harness | skill 落点 | 说明 |
|---|---|---|
| `qoder` | `.qoder/skills/` | 项目级自动识别 |
| `codex` | `.agents/skills/` | Codex 官方位置（仓库根 / 当前目录 / 祖先目录都会扫描）；用 `$srm-feature` 或 `/skills` 显式调用，也按 `description` 自动匹配 |
| `dsh` | `.dsh/skills/` | DSH 同时扫描 `.agents/skills/`，所以为 Codex 装一次对 DSH 也生效 |
| `none` | 不装 | 只用 runner |

**`.codex/prompts` 不是 skill 位置**，装在那里 Codex 不会当成 skill 加载。

skill 采用渐进式披露：Codex 初始列表只读 `name` 和 `description`（默认上限为上下文的 2%），
命中后才读完整 `SKILL.md`。所以 `description` 里要前置触发词——本插件的两个 skill 已经这么写。

## 输出怎么读

`check` 分三级：

- **[阻断]** 新增不变量违规、超大文件变大、新增超大文件 → 必须处理
- **[警告]** 范围预算超限、测试气味 → 自己判断；确认合理就改 policy 并写理由
- **基线行** 只显示"已冻结多少项"，不逐条列

`audit` 只回答一个问题：**这周该动哪个文件**。给的是排序和"从哪里看起"，不是问题清单。

## 优化口子（重要）

首版没经过长期使用，判定阈值是估的。留了三个入口，供后续按真实数据调整：

| 入口 | 内容 | 用途 |
|---|---|---|
| `.archguard/runs/*.json` | 每次 `check` 的完整记录：改动量、新增违规、阻断结果、耗时 | 看规则是否过严/过松 |
| `devguard.py feedback --key <键> --verdict noise` | 人工标注"这条提示是噪声" | 我据此删规则或调阈值 |
| `.archguard/policy.json` | 全部阈值与开关 | 你自己就能调，不用等我改代码 |
| `devguard.py report` | 汇总以上三项 | 把这个输出发我即可迭代 |

典型用法：某个检查连续三次被标 `noise` → 直接关掉或收窄；某个检查从没触发 → 说明阈值太松或规则没覆盖到。

## 已知限制

- 检查用正则，不解析完整语法树：结论是**候选**，需人确认
- 变更量统计基于 `git diff`，未跟踪文件会计入；非 git 目录下 `check` 不可用
- 不跑 Maven、不跑测试：它的定位是"看结构"，不是"验证行为"
- `review` 只判可机械判定的部分；设计文档若没有完整可执行 SQL，表数约束会明确标为"未验证"而不是"通过"
