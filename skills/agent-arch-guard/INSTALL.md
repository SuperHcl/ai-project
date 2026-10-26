# 安装与同步指南

> 一套源文件，装到三个 harness。所有落地路径均按各工具实测约定实现，不猜测。

## 前置

1. Python 3.9+（`py -3` / `python` / `python3` 任一在 PATH）
2. Git（只用来自查仓库根与安装 hook，不联网）

## 一键安装

```powershell
# 目标项目已在用哪个 harness，就装哪个
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Project d:\workspaces\ai\srm -Harness all

# 只装 Qoder
.\install.ps1 -Project d:\workspaces\ai\srm -Harness qoder

# 预览（不落盘）
.\install.ps1 -Project d:\workspaces\ai\srm -Harness all -DryRun
```

跨平台等价命令：

```bash
python -I scripts/install.py --project /path/to/project --harness all
```

`-Harness auto`（默认）按目录探测：存在 `.qoder` → qoder，`.dsh` → dsh，`.codex` 或 `~/.codex` → codex。探测不到会报错并提示显式指定。

## 各 harness 落点

| Harness | Skill | 常驻规则 |
|---|---|---|
| Qoder | `<项目>/.qoder/skills/archg-*/SKILL.md` | `<项目>/.qoder/rules/arch-guard.md` |
| DSH | `<项目>/.dsh/skills/archg-*/SKILL.md` | `AGENTS.md` 内标记块 |
| Codex | `<项目>/.codex/prompts/archg-*.md` | `AGENTS.md` 内标记块 |
| 三者共用 | `<项目>/.arch-guard/{ratchet,scan_design,verify}.py` | — |

用户级安装（`--user-level`）：DSH → `$DSH_HOME/skills`（默认 `~/.dsh/skills`）；Codex → `~/.codex/prompts`。Qoder 仅支持项目级。

## AGENTS.md 标记块

安装器只在下面两行之间写内容，块外一律不改：

```markdown
<!-- arch-guard:begin -->
...（rules/AGENT.md 的内容）
<!-- arch-guard:end -->
```

- 已存在则替换块内内容（幂等，重复安装不产生 diff）
- 不存在则追加到文件末尾；`AGENTS.md` 不存在则新建
- 卸载：直接删除这两行之间的内容即可

## 安装 Git 门禁（可选）

```powershell
.\install.ps1 -Project d:\workspaces\ai\srm -Harness all -WithHook
```

- 写入 `.git/hooks/pre-commit`，执行 `verify.py --fast`
- 若已存在**非本插件管理**的 pre-commit，安装器**拒绝覆盖**并报错退出（与项目已有 hook 共存需人工合并）
- 只读当前检出，不跑 Maven、不联网、不改文件

## 安装后必做

```bash
# 1. 记录现状基线（把已超标的文件冻结，之后只许变小）
python -I .arch-guard/ratchet.py --init

# 2. 提交 .arch-guard/baseline.json 与 .arch-guard/budget.json，否则门禁不生效
git add .arch-guard/

# 3. 自检
python -I .arch-guard/verify.py
```

预算文件 `.arch-guard/budget.json` 由安装器在缺失时生成，默认值：

```json
{ "max_files": 40, "max_added_lines": 800, "max_new_endpoints": 5, "max_new_tables": 2 }
```

按项目实际调整，**不要为了让检查通过而调高**；要调必须写理由并让人确认。

## 自检与验证

```bash
# 安装器自检（临时目录，验证三 harness 落地 / 幂等 / 块外保留 / 外来 hook 拒绝覆盖）
python -I scripts/install.py --self-check

# 设计扫描（只报告，不改判定）
python -I .arch-guard/scan_design.py --src <源码根>

# 旧代码体检：改造候选排序
python -I .arch-guard/audit.py --root . --src <源码根> --top 20

# 范围预算（交付前 / CI）
python -I .arch-guard/scope_check.py --root .
python -I .arch-guard/scope_check.py --root . --base origin/main

# 棘轮校验
python -I .arch-guard/ratchet.py --check
```

## 升级

```bash
git -C <插件仓> pull
python -I scripts/install.py --project <目标项目> --harness all
```

内容一致的文件会跳过，不产生无意义 diff。`--force` 才强制覆盖（谨慎：会覆盖你在项目侧手改过的检查器副本）。

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| `未探测到 .qoder / .dsh / .codex` | 显式传 `--harness` |
| hook 安装失败：已存在非本插件管理的 pre-commit | 项目已有 hook；手工把 `exec ... verify.py --fast` 合并进去 |
| `verify.py` 报 `未找到基线` | 先跑 `ratchet.py --init` 并提交 baseline |
| 棘轮把所有文件都判失败 | baseline 未提交或不匹配当前分支；确认 `.arch-guard/baseline.json` 在版本库内 |
| 想让某个大文件合法变大 | 拆分；或 `--update --force-raise` 并由人确认（刻意保留摩擦） |
| Codex 里斜杠命令看不到 | Codex 可能只读用户级 prompt：加 `--user-level` 重装 |
