#!/usr/bin/env python3
"""SRM DevGuard —— 本地唯一入口。

两个动作，两件事：
  check  新需求/改动交付前：只报「本次新增」的问题（存量已冻结，不制造噪声）
  audit  旧代码从哪开始看：按「复杂度 x 变更热度」排改造候选

设计取舍（刻意不做的东西）：
  - 不做流程状态机、不做多步编排、不产编号文档：单人 + Agent 下维护流程本身就是负担
  - 不报存量问题：5019 个文件里存量问题一片，全量报等于没人看
  - 不新建文档目录：产物全部落在 .archguard/（本地，自动加入 .git/info/exclude）

命令：
  python -I .archguard/devguard.py init                 # 冻结现状（基线）+ 生成策略文件
  python -I .archguard/devguard.py check                # 交付前自检
  python -I .archguard/devguard.py check --base origin/main --strict-budget
  python -I .archguard/devguard.py audit --top 15       # 旧代码改造候选
  python -I .archguard/devguard.py audit --file <某个类>  # 单类体检
  python -I .archguard/devguard.py feedback --key <键> --verdict noise
  python -I .archguard/devguard.py report               # 汇总，用于后续调参
  python -I .archguard/devguard.py install --harness qoder|dsh|codex

退出码：0 通过 / 1 有阻断项 / 2 配置或用法错误
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

STATE_DIR = ".archguard"
POLICY_REL = STATE_DIR + "/policy.json"
BASELINE_REL = STATE_DIR + "/baseline.json"
RUNS_REL = STATE_DIR + "/runs"
FEEDBACK_REL = STATE_DIR + "/feedback.jsonl"

_STATE_ROOT = None


def state_dir(root):
    """状态目录。默认写在仓库内 .archguard/；--state 可外置（只读运行、CI）。"""
    return Path(_STATE_ROOT).resolve() if _STATE_ROOT else (root / STATE_DIR)

DEFAULT_POLICY = {
    "version": 1,
    "modules": {
        "common": "srm-common/src/main/java",
        "feign": "srm-feign/src/main/java",
        "server": "srm-server/src/main/java",
    },
    "scanRoots": ["srm-common/src", "srm-feign/src", "srm-server/src"],
    "excludeDirs": [".git", "target", "build", "node_modules", ".idea", ".vscode", ".archguard"],
    "budgets": {
        "max_files": 40,
        "max_added_lines": 800,
        "max_new_endpoints": 5,
        "max_new_tables": 2,
    },
    "godFile": {"trackLines": 800, "newFileLimit": 600},
    "audit": {"churnSince": "90 days ago", "top": 15, "godLines": 400},
    "review": {
        # 与 .agent/db-rule.md:23 一致：多表 join ≤3 张
        "maxJoinTables": 3,
        "requiredDiagrams": ["sequenceDiagram", "flowchart", "erDiagram"],
        "requireTestMatrix": True,
        "roles": [],
        "hintPatterns": ["内存分页", "subList", "分页后合并", "全表扫描", "各角色分页"],
    },
    "checks": {
        "flowableImport": True,
        "jdk9Api": True,
        "entityLeak": True,
        "controllerLayout": True,
        "feignContextId": True,
        "thirdFormMixing": True,
        "testSmell": True,
    },
}

FLOWABLE_RE = re.compile(r"\bimport\s+org\.flowable\.")
JDK9API_RE = re.compile(
    r"\b(?:List|Map|Set)\.of\s*\(|@Serial\b|\brecord\s+\w+\s*\(|\bvar\s+\w+\s*=|\"\"\"")
ENTITY_IMPORT_RE = re.compile(r"\bimport\s+com\.mxbc\.srm\.server\.base\.entity\.")
CONTROLLER_PATH_RE = re.compile(r"/controller/(?:(?:pc|app)/(?:staff|partner)|internal|common|shared)/")
FEIGN_CLIENT_RE = re.compile(r"@FeignClient\s*\((.*?)\)", re.S)
THIRD_MIX_RE = re.compile(r"\bimport\s+com\.mxbc\.srm\.server\.base\.domain\.(?:form|vo)\.")
ENDPOINT_RE = re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping")
TABLE_RE = re.compile(r"@TableName|CREATE\s+TABLE", re.I)
VERIFY_RE = re.compile(r"^\s*verify\s*\(", re.M)
TEST_EXTS = {".java"}
ENDPOINT_EXTS = {".java", ".kt"}
TABLE_EXTS = {".java", ".sql", ".xml"}


# ── 基础工具 ────────────────────────────────────────────────────────────────


def load_policy(root, create=False):
    target = state_dir(root) / "policy.json"
    if not target.exists():
        if not create:
            return DEFAULT_POLICY, target, False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(DEFAULT_POLICY, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        return DEFAULT_POLICY, target, True
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"策略文件无法解析：{target}（{error}）")
    merged = json.loads(json.dumps(DEFAULT_POLICY))
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged, target, True


def iter_files(root, subdirs, exts, exclude_dirs):
    for subdir in subdirs:
        base = root / subdir
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
            if any(part in exclude_dirs for part in path.parts):
                continue
            yield path


def read_lines(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def line_count(path):
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)


def rel_of(root, path):
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode, result.stdout.decode("utf-8", "replace")


# ── 不变量检查（SRM 特有，只报新增）────────────────────────────────────────


def check_invariants(root, policy):
    """返回 [(key, file, line, message)]。key 不含行号，便于基线跨改动稳定。"""
    exclude = set(policy["excludeDirs"])
    findings = []
    modules = policy["modules"]
    common_feign = [modules["common"], modules["feign"]]

    for path in iter_files(root, policy["scanRoots"], {".java"}, exclude):
        rel = rel_of(root, path)
        lines = read_lines(path)
        in_common_feign = any(rel.startswith(item) for item in common_feign)
        in_third = "/third/" in "/" + rel
        in_base = "/base/" in "/" + rel
        in_controller = "/controller/" in "/" + rel
        in_feign = rel.startswith(modules["feign"])

        for number, line in enumerate(lines, 1):
            if policy["checks"]["flowableImport"] and rel.startswith(modules["server"]) \
                    and FLOWABLE_RE.search(line):
                findings.append(("flowable-import", rel, number, "srm-server 禁止 import org.flowable.*"))
            if policy["checks"]["jdk9Api"] and in_common_feign and JDK9API_RE.search(line):
                findings.append(("jdk9-api", rel, number, "common/feign 必须 Java 8 字节码，禁用 JDK9+ API"))
            # Entity 不出 base 包：真正的含义是不得出现在对外契约（Controller 出入参、feign DTO）里。
            # 跨域内部引用 Entity 是现状常态，不作为违规。
            if policy["checks"]["entityLeak"] and (in_controller or in_feign) \
                    and ENTITY_IMPORT_RE.search(line):
                findings.append(("entity-leak", rel, number,
                                 "Entity 不得出现在 Controller 出入参或 feign 契约中"))
            if policy["checks"]["thirdFormMixing"] and in_third and THIRD_MIX_RE.search(line):
                findings.append(("third-form-mixing", rel, number, "第三方参数类不得与业务 Form/Vo 混用"))

        if policy["checks"]["controllerLayout"] and path.name.endswith("Controller.java") \
                and "/controller/" in "/" + rel and not CONTROLLER_PATH_RE.search("/" + rel):
            findings.append(("controller-layout", rel, 0,
                             "Controller 必须落在 controller/{pc,app}/{staff,partner} 或 internal/common/shared"))

        if policy["checks"]["feignContextId"] and "@FeignClient" in "\n".join(lines):
            for match in FEIGN_CLIENT_RE.finditer("\n".join(lines)):
                if "contextId" not in match.group(1):
                    line_no = "\n".join(lines)[: match.start()].count("\n") + 1
                    findings.append(("feign-context-id", rel, line_no, "@FeignClient 必须显式声明唯一 contextId"))

    return findings


def finding_key(item):
    check, rel, _line, message = item
    return f"{check}|{rel}|{message}"


# ── 棘轮：超大文件只许变小 ──────────────────────────────────────────────────


def scan_god_files(root, policy):
    exclude = set(policy["excludeDirs"])
    track = policy["godFile"]["trackLines"]
    result = {}
    for path in iter_files(root, policy["scanRoots"], {".java"}, exclude):
        count = line_count(path)
        if count >= track:
            result[rel_of(root, path)] = count
    return result


# ── 范围预算：基于 git diff ────────────────────────────────────────────────


def scan_changes(root, base):
    diff = ["diff", base]
    code, numstat = git(root, *(diff + ["--numstat"]))
    files = added = deleted = 0
    biggest = []
    endpoints = tables = 0

    current = ""
    code, unified = git(root, *(diff + ["-U0"]))
    for line in unified.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        suffix = Path(current).suffix.lower()
        if suffix in ENDPOINT_EXTS and ENDPOINT_RE.search(line):
            endpoints += 1
        if suffix in TABLE_EXTS and TABLE_RE.search(line):
            tables += 1

    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "-":
            continue
        add, rem, path = parts
        files += 1
        added += int(add)
        deleted += int(rem)
        biggest.append((int(add), path))

    code, untracked = git(root, "ls-files", "--others", "--exclude-standard")
    for rel in untracked.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        path = root / rel
        if not path.is_file():
            continue
        text = "\n".join(read_lines(path))
        suffix = path.suffix.lower()
        files += 1
        added += line_count(path)
        if suffix in ENDPOINT_EXTS:
            endpoints += len(ENDPOINT_RE.findall(text))
        if suffix in TABLE_EXTS:
            tables += len(TABLE_RE.findall(text))
        biggest.append((line_count(path), rel + "（新增）"))

    return {"files": files, "added": added, "deleted": deleted,
            "endpoints": endpoints, "tables": tables, "biggest": biggest}


def scan_test_smells(root, base):
    """只查本次新增/修改的测试代码，避免存量噪声。"""
    code, names = git(root, "diff", base, "--name-only", "--diff-filter=AM")
    candidates = [item.strip() for item in names.splitlines() if item.strip()]
    code, untracked = git(root, "ls-files", "--others", "--exclude-standard")
    candidates += [item.strip() for item in untracked.splitlines() if item.strip()]

    findings = []
    for rel in candidates:
        if "/src/test/" not in "/" + rel or Path(rel).suffix.lower() not in TEST_EXTS:
            continue
        path = root / rel
        if not path.is_file():
            continue
        text = "\n".join(read_lines(path))
        for match in VERIFY_RE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            findings.append(("test-verify-on-collaborator", rel, line,
                             "测试断言协作者被调用次数属于实现细节，改为断言业务结果"))
        if "@Disabled" in text or "@Ignore" in text:
            line = text[: text.find("@Disabled" if "@Disabled" in text else "@Ignore")].count("\n") + 1
            findings.append(("test-disabled", rel, line, "新增被禁用的测试等于没有测试"))
    return findings


# ── 基线 ────────────────────────────────────────────────────────────────────


def load_baseline(root):
    target = state_dir(root) / "baseline.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(f"基线无法解析：{target}，请重新 init")


def save_baseline(root, payload):
    target = state_dir(root) / "baseline.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_run(root, command, payload):
    folder = state_dir(root) / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = folder / f"{stamp}-{command}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_excluded(root):
    """SRM 规范禁止新增文档目录入库，这里自动把状态目录排除掉。

    仓库可能在别处不可写（沙箱/权限/CI 只读挂载），失败不算错——这种情况用 --state 外置。
    """
    try:
        code, git_dir = git(root, "rev-parse", "--absolute-git-dir")
        if code != 0:
            return False
        exclude = Path(git_dir.strip()) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        content = exclude.read_text(encoding="utf-8", errors="replace") if exclude.exists() else ""
        pattern = state_dir(root).name + "/"
        if pattern in content.splitlines():
            return False
        with exclude.open("a", encoding="utf-8") as handle:
            if content and not content.endswith("\n"):
                handle.write("\n")
            handle.write(pattern + "\n")
        return True
    except OSError:
        return False


# ── 命令 ────────────────────────────────────────────────────────────────────


def cmd_init(root, args):
    policy, policy_path, created = load_policy(root, create=True)
    findings = check_invariants(root, policy)
    god = scan_god_files(root, policy)
    save_baseline(root, {
        "version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "存量问题已冻结；check 只报新增项。收敛后重跑 init 收紧。",
        "invariants": sorted({finding_key(item) for item in findings}),
        "godFiles": {key: god[key] for key in sorted(god)},
    })
    excluded = ensure_excluded(root)

    print(f"# 基线已生成：{state_dir(root) / 'baseline.json'}")
    if created:
        print(f"# 策略已生成：{state_dir(root) / 'policy.json'}（改这里可调阈值，不用改代码）")
    print(f"- 冻结不变量问题：{len({finding_key(item) for item in findings})} 项")
    breakdown = Counter(item[0] for item in findings)
    if breakdown:
        print("  " + " / ".join(f"{name} {count}" for name, count in breakdown.most_common()))
    print(f"- 冻结超大文件：{len(god)} 个（>= {policy['godFile']['trackLines']} 行，"
          f"合计 {sum(god.values())} 行）")
    if excluded:
        print(f"- 已把 {STATE_DIR}/ 加入 .git/info/exclude（不污染仓库，符合项目文档规则）")
    hot = sorted(god.items(), key=lambda item: -item[1])[:3]
    for rel, count in hot:
        print(f"  {count:>6} 行  {rel}")
    return 0


def cmd_check(root, args):
    policy, _, exists = load_policy(root)
    if not exists:
        print(f"缺少策略文件：{POLICY_REL}，先执行 init", file=sys.stderr)
        return 2
    baseline = load_baseline(root)
    if baseline is None:
        print(f"缺少基线：{BASELINE_REL}，先执行 init", file=sys.stderr)
        return 2

    started = time.time()
    findings = check_invariants(root, policy)
    known = set(baseline.get("invariants", []))
    new_findings = [item for item in findings if finding_key(item) not in known]

    god_now = scan_god_files(root, policy)
    god_base = baseline.get("godFiles", {})
    god_grown = [(rel, god_base[rel], lines) for rel, lines in god_now.items()
                 if rel in god_base and lines > god_base[rel]]
    god_new = [(rel, lines) for rel, lines in god_now.items()
               if rel not in god_base and lines >= policy["godFile"]["newFileLimit"]]

    changes = scan_changes(root, args.base)
    budgets = policy["budgets"]
    over = []
    for name, key in (("文件数", "files"), ("新增行", "added"), ("新增端点", "endpoints"),
                      ("新增表", "tables")):
        limit = budgets.get("max_" + {"文件数": "files", "新增行": "added_lines",
                                      "新增端点": "new_endpoints", "新增表": "new_tables"}[name])
        if limit is not None and changes[key] > limit:
            over.append((name, changes[key], limit))

    smells = scan_test_smells(root, args.base) if policy["checks"]["testSmell"] else []

    blocked = bool(new_findings or god_grown or god_new or (args.strict_budget and over))

    print("# DevGuard check\n")
    print(f"- 基线：{len(known)} 项存量不变量问题 / {len(god_base)} 个超大文件（已冻结，不再报）")
    print(f"- 本次改动：{changes['files']} 文件 / +{changes['added']} 行 / "
          f"+{changes['endpoints']} 端点 / +{changes['tables']} 表\n")

    def dump(title, items, formatter):
        if not items:
            return
        print(f"## {title}（{len(items)}）")
        for item in items:
            print("  - " + formatter(item))
        print()

    dump("新增不变量违规 [阻断]", new_findings,
         lambda item: f"{item[0]}  {item[1]}:{item[2]}  {item[3]}")
    dump("超大文件变大 [阻断]", god_grown,
         lambda item: f"{item[0]}  {item[1]} -> {item[2]} 行（+{item[2] - item[1]}）")
    dump("新增超大文件 [阻断]", god_new,
         lambda item: f"{item[0]}  {item[1]} 行（新文件上限 {policy['godFile']['newFileLimit']}）")
    dump(("范围预算超限 " + ("[阻断]" if args.strict_budget else "[警告]")), over,
         lambda item: f"{item[0]}：{item[1]} > {item[2]}")
    dump("测试气味 [警告]", smells,
         lambda item: f"{item[0]}  {item[1]}:{item[2]}  {item[3]}")

    if changes["biggest"] and changes["files"]:
        print("改动最大的文件：")
        for count, path in sorted(changes["biggest"], reverse=True)[:5]:
            print(f"  +{count:<5} {path}")
        print()

    record_run(root, "check", {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base": args.base,
        "duration_ms": int((time.time() - started) * 1000),
        "changes": {key: changes[key] for key in ("files", "added", "endpoints", "tables")},
        "new_invariants": [{"key": finding_key(item), "file": item[1], "line": item[2],
                            "message": item[3]} for item in new_findings],
        "god_grown": len(god_grown), "god_new": len(god_new),
        "budget_over": [name for name, _, _ in over],
        "smells": len(smells),
        "blocked": blocked,
    })

    if blocked:
        print("[未通过] 先处理上面的阻断项。确实合理时，改策略文件并说明理由，不要跳过检查。")
        return 1
    print("[通过] 可以交付。警告项请自行判断是否为真问题。")
    return 0


def churn_map(root, since):
    code, text = git(root, "log", "--pretty=format:", "--name-only", f"--since={since}")
    if code != 0:
        return {}
    return Counter(line.strip() for line in text.splitlines() if line.strip())


def complexity(path):
    lines = line_count(path)
    texts = read_lines(path)
    publics = sum(1 for line in texts
                  if re.match(r"^\s{0,8}public\s+", line) and "(" in line)
    imports = sum(1 for line in texts if line.lstrip().startswith("import "))
    return lines, publics, imports


def cmd_audit(root, args):
    policy, _, _ = load_policy(root)
    exclude = set(policy["excludeDirs"])
    since = args.since or policy["audit"]["churnSince"]
    top = args.top or policy["audit"]["top"]
    churn = churn_map(root, since)

    if args.file:
        candidates = (root / args.file).is_file() and [root / args.file] or [
            p for p in iter_files(root, policy["scanRoots"], {".java"}, exclude)
            if Path(args.file).stem.lower() in p.name.lower()]
        targets = candidates[:5]
        if not targets:
            print(f"找不到匹配文件：{args.file}", file=sys.stderr)
            return 2
    else:
        targets = list(iter_files(root, policy["scanRoots"], {".java"}, exclude))
        if not args.include_tests:
            targets = [p for p in targets if "/src/test/" not in "/" + rel_of(root, p)]

    items = []
    for path in targets:
        lines, publics, imports = complexity(path)
        rel = rel_of(root, path)
        changes = churn.get(rel, 0)
        score = (lines / 200.0 + publics / 10.0 + imports / 20.0) * (1.0 + 0.0)
        score *= (1.0 + (changes ** 0.5) / 3.0)
        tags = []
        if lines >= policy["godFile"]["trackLines"]:
            tags.append("巨型")
        elif lines >= policy["audit"]["godLines"]:
            tags.append("偏大")
        if publics >= 40:
            tags.append("接口面大")
        if imports >= 60:
            tags.append("依赖过多")
        if changes >= 10:
            tags.append("高频改动")
        items.append({"file": rel, "lines": lines, "publics": publics, "imports": imports,
                      "changes": changes, "score": round(score, 1), "tags": tags})

    items.sort(key=lambda item: -item["score"])
    if args.json:
        print(json.dumps({"since": since, "items": items[:top]}, ensure_ascii=False, indent=2))
        return 0

    if args.file:
        item = items[0]
        label = since.replace(" days ago", " 天").replace(" day ago", " 天")
        print(f"# 单类体检：{item['file']}\n")
        print(f"- 行数 {item['lines']} / 公开方法 {item['publics']} / 依赖 {item['imports']} "
              f"/ 近 {label}改动 {item['changes']} 次")
        print(f"- 标签：{' '.join(item['tags']) or '无明显问题'}\n")
        steps = []
        if "接口面大" in item["tags"]:
            steps.append("先把 public 方法按调用方分组：哪些给本域用、哪些给外部用、哪些没人用")
            steps.append("没人用的先删；只给本域用的降为包内可见")
        if "巨型" in item["tags"]:
            steps.append("找状态字段（`set` 写它的地方）：同一份状态多处可写 → 先收口到一处")
            steps.append("找 `@Transactional`：看它是否包住了远程调用（长事务）或多写未包（半成功）")
        if "依赖过多" in item["tags"]:
            steps.append("看 import 最多的那几个依赖：是不是应该收进一个门面类")
        steps.append("找 `catch` 后只 log 或 return null 的地方：失败被当成成功，最贵的一类")
        print("## 从哪里看起")
        for index, step in enumerate(steps, 1):
            print(f"{index}. {step}")
        return 0

    print("# DevGuard audit（旧代码改造候选）\n")
    print(f"- 扫描 {len(items)} 个文件；热度窗口 {since}")
    print("- 排序：复杂度（行/公开方法/依赖）x 变更热度；只改「又大又还在动」的\n")
    print("| # | 文件 | 行 | 公开方法 | 改动 | 标签 | 分数 |")
    print("|---|---|---|---|---|---|---|")
    for index, item in enumerate(items[:top], 1):
        print(f"| {index} | `{item['file']}` | {item['lines']} | {item['publics']} "
              f"| {item['changes']} | {' '.join(item['tags']) or '-'} | {item['score']} |")
    hot = [item for item in items if "高频改动" in item["tags"]]
    print(f"\n> 本轮不碰：{len(items) - len(hot)} 个文件不在近期改动范围。"
          f"除非需求正好要动它，否则不要顺手重构。")
    print("> 单个文件怎么看：`devguard.py audit --file <类名或路径>`")
    return 0


SYMBOL_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9]{2,}(?:Service|ServiceImpl|Dao|Mapper|Entity|Controller|Cache|CacheData|"
    r"Vo|Form|Converter|Manager|Support|Registry|Policy|Component|Helper|Client|Engine|Port))\b")
METHOD_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+)\.([a-z][A-Za-z0-9]*)\s*\(")
CODE_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.S)
TABLE_REF_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", re.I)


def build_class_index(code_root, exclude):
    index = {}
    for path in iter_files(code_root, ["."], {".java"}, exclude):
        index.setdefault(path.stem, path)
    return index


def cmd_review(root, args):
    """设计文档机械预检：只判"可机械判定的部分"，不做语义裁决。"""
    doc = Path(args.doc)
    if not doc.is_file():
        print(f"文档不存在：{doc}", file=sys.stderr)
        return 2
    policy, _, _ = load_policy(root)
    settings = policy["review"]
    code_root = Path(args.code).resolve() if args.code else root
    text = doc.read_text(encoding="utf-8", errors="replace")
    blocks = [(m.group(1).lower(), m.group(2)) for m in CODE_FENCE_RE.finditer(text)]
    roles = [item.strip() for item in
             ((args.roles or "").split(",") if args.roles else settings["roles"]) if item.strip()]

    failures, hints = [], []

    for kind in settings["requiredDiagrams"]:
        if kind not in text:
            failures.append(("缺少必备图", kind))

    # 测试矩阵：不苛求字面叫“测试矩阵”，有“测试对象/必测场景/用例/场景+预期”表也算
    if settings["requireTestMatrix"] and not re.search(
            r"测试矩阵|\|[^|]*(测试对象|必测场景|用例|场景)[^|]*\|", text):
        failures.append(("缺少测试矩阵", "没有“测试矩阵”字样，也没有“测试对象/必测场景/用例/场景”表头"))

    for role in roles:
        if role not in text:
            failures.append(("角色未覆盖", role))

    # 只有"像完整语句"的块才计入表数：SELECT + FROM + (WHERE/JOIN/GROUP BY)。
    # 文档里常见的谓词片段（自述"不是可直接执行的完整 SQL"）不能拿来核表数。
    candidate_sql = [body for lang, body in blocks
                     if lang == "sql" or re.search(r"\bselect\b", body, re.I)]

    def looks_executable(body):
        """去掉注释后必须以 SELECT / <select> 开头，才算完整语句；否则是谓词片段。"""
        stripped = re.sub(r"(?m)^\s*--.*$", "", body).strip()
        return bool(re.match(r"(?is)^(?:<select[^>]*>|select\b)", stripped)) \
            and bool(re.search(r"(?is)\bfrom\b", stripped))

    executable_sql = [body for body in candidate_sql if looks_executable(body)]
    max_tables = 0
    for part in executable_sql:
        tables = {name.split(".")[-1] for name in TABLE_REF_RE.findall(part)}
        max_tables = max(max_tables, len(tables))
        if len(tables) > settings["maxJoinTables"]:
            failures.append(("SQL 关联表数超限",
                             f"{len(tables)} 张表 > {settings['maxJoinTables']}：{', '.join(sorted(tables))}"))

    # 符号核对：图里的名字是设计节点（形如 UserService[SysUserService] 的节点 id），不是代码事实。
    # 先剔除 mermaid，再在正文里区分“新增”与“现状”，只报未标注新增又确实不存在的。
    plan_words = ("新增", "拟", "建议", "设计为", "改为", "引入", "拆分", "下沉", "抽出",
                  "新建", "不再", "抽取", "替换")
    body_text = re.sub(r"```mermaid.*?```", "", text, flags=re.S)
    body_lines = body_text.splitlines()
    occurrences = {}
    for match in SYMBOL_RE.finditer(body_text):
        name = match.group(1)
        bucket = occurrences.setdefault(name, {"plan": 0, "plain": 0})
        # 只按同一行判定：上下行常属于别的话题，带上会误判
        line_index = body_text[: match.start()].count("\n")
        context = body_lines[line_index] if line_index < len(body_lines) else ""
        if any(word in context for word in plan_words):
            bucket["plan"] += 1
        else:
            bucket["plain"] += 1

    index = build_class_index(code_root, set(policy["excludeDirs"]))
    symbols = sorted(occurrences)
    # 只要文档里任一非图位置标了“新增/抽取/改为…”，就认作已声明的新类，不做事实核对。
    planned = [name for name, item in occurrences.items()
               if name not in index and item["plan"]]
    missing = [name for name, item in occurrences.items()
               if name not in index and not item["plan"]]
    unlabeled = missing
    missing_methods = []
    for cls, method in sorted(set(METHOD_RE.findall(body_text))):
        path = index.get(cls)
        if path is None:
            continue
        try:
            if method + "(" not in path.read_text(encoding="utf-8", errors="replace"):
                missing_methods.append(f"{cls}.{method}()")
        except OSError:
            continue

    # 代码事实核对默认是提示：文档里"写的是计划还是现状"需要人判断，不适合机械阻断。
    if args.strict_facts:
        for name in missing:
            failures.append(("事实核对失败", f"代码中不存在且未标注新增：{name}"))

    # 提示项要排除“禁止性表述”：文档里写“不得用内存分页”不该被当成违规写法
    negations = ("禁止", "不得", "严禁", "不允许", "不可", "不用", "不能", "不把", "不做",
                 "避免", "而非", "拒绝", "不采用", "不新增")
    for pattern in settings["hintPatterns"]:
        for match in re.finditer(re.escape(pattern), text):
            window_start = max(text.rfind("。", 0, match.start()),
                               text.rfind("\n", 0, match.start()),
                               text.rfind("；", 0, match.start()),
                               text.rfind(";", 0, match.start()))
            sentence = text[window_start + 1: match.end() + 40]
            if any(word in sentence for word in negations):
                continue
            hints.append((pattern, text[: match.start()].count("\n") + 1))

    payload = {"doc": str(doc), "lines": text.count("\n") + 1,
               "symbols_checked": len(symbols), "missing_symbols": missing,
               "planned_symbols": planned, "unlabeled_symbols": unlabeled,
               "missing_methods": missing_methods,
               "failures": [{"check": item[0], "detail": item[1]} for item in failures],
               "sql_complete": len(executable_sql), "sql_max_tables": max_tables,
               "hints": [{"pattern": item[0], "line": item[1]} for item in hints]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if failures else 0

    print("# DevGuard review（设计文档机械预检）\n")
    print(f"- 文档：{doc.name}（{payload['lines']} 行，{len(blocks)} 段代码）")
    print(f"- 代码基线：{code_root}")
    print(f"- 角色检查：{', '.join(roles) if roles else '未配置（用 --roles 指定）'}\n")

    if failures:
        print(f"## 机械判定未通过（{len(failures)}）")
        for item in failures:
            print(f"  - [{item[0]}] {item[1]}")
        print()
    else:
        print("## 机械判定\n  - 结构、角色覆盖、SQL 表数均通过\n")

    print("## SQL 核验")
    if executable_sql:
        print(f"  - 完整语句 {len(executable_sql)} 段，最大去重表数 {max_tables}"
              f"（上限 {settings['maxJoinTables']}）")
    elif candidate_sql:
        print(f"  - 未发现完整可执行 SQL（有 {len(candidate_sql)} 段谓词片段）；"
              f"表数约束未被机械验证 —— 实施前必须补完整语句")
    else:
        print("  - 文档中没有 SQL；表数约束未被机械验证 —— 实施前必须补完整语句")
    print()

    print("## 代码事实核对")
    if missing or missing_methods:
        for name in missing[:15]:
            print(f"  - 代码中不存在，且文档未标为新增：`{name}`")
        for name in missing_methods[:15]:
            print(f"  - 已存在类中找不到方法：`{name}`")
        if len(missing) + len(missing_methods) > 30:
            print(f"  - ... 其余 {len(missing) + len(missing_methods) - 30} 项省略（--json 看全部）")
    else:
        print(f"  - {len(symbols)} 个符号：已存在的都在代码中命中，其余均标注为新增")
    if planned:
        print(f"  - 拟新增（文档已标注，不做事实核对）：{len(planned)} 个")
    print()

    if hints:
        print("## 需要与硬约束对照的写法（提示，不是判决）")
        for pattern, line in hints[:12]:
            print(f"  - 第 {line} 行出现「{pattern}」：核对是否触犯“禁止无界 IN / 内存分页 / 分页后合并”")
        print()

    print("## 无法自动判断（必须人工）")
    print("  - 权限语义是否正确（多角色并集、顶层交集、无角色不得放行）")
    print("  - 缓存一致性与撤权时效是否可接受（TTL / 主动失效 / 失败补偿）")
    print("  - 设计是否与真实业务口径一致（本文凭据只覆盖“与代码是否自洽”）")
    print("  - 迁移顺序与分阶段是否可执行")

    record_run(root, "review", {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "doc": str(doc),
                                "failures": len(failures), "missing_symbols": len(missing),
                                "missing_methods": len(missing_methods)})
    return 1 if failures else 0


def cmd_feedback(root, args):
    target = state_dir(root) / "feedback.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "key": args.key,
        "verdict": args.verdict,
        "note": args.note or "",
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"已记录：{args.verdict}  {args.key}")
    return 0


def cmd_report(root, args):
    runs_dir = state_dir(root) / "runs"
    runs = sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
    print("# DevGuard report（用于后续调参）\n")
    if not runs:
        print("还没有运行记录。跑几次 check 之后再看。")
    else:
        print(f"- 运行记录：{len(runs)} 次（最近 {min(len(runs), args.limit)} 次）\n")
        print("| 时间 | 命令 | 改动 | 新增违规 | 阻断 | 耗时 |")
        print("|---|---|---|---|---|---|")
        for path in runs[-args.limit:]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            changes = data.get("changes", {})
            print(f"| {data.get('at', '')} | {path.stem.split('-', 2)[-1]} "
                  f"| {changes.get('files', 0)} 文件/+{changes.get('added', 0)} 行 "
                  f"| {len(data.get('new_invariants', []))} "
                  f"| {'是' if data.get('blocked') else '否'} "
                  f"| {data.get('duration_ms', 0)}ms |")

        counter = Counter()
        for path in runs:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for item in data.get("new_invariants", []):
                counter[item.get("message", "")] += 1
        if counter:
            print("\n## 被触发最多的检查（判断是不是噪声太多）")
            for message, count in counter.most_common(8):
                print(f"- {count} 次  {message}")

    feedback_path = state_dir(root) / "feedback.jsonl"
    if feedback_path.exists():
        entries = []
        for line in feedback_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
        if entries:
            tally = Counter(item["verdict"] for item in entries)
            print(f"\n## 人工反馈：{dict(tally)}")
            noise = [item for item in entries if item["verdict"] == "noise"][:10]
            for item in noise:
                print(f"- [噪声] {item['key']}  {item.get('note', '')}")

    print("\n把这个 report 的输出（或 .archguard/ 整个目录）交给维护者，用来调阈值和加规则。")
    return 0


def skill_root(root, harness, user_level):
    """各 harness 的 skill 落点。

    Codex 读 .agents/skills（官方：仓库根/当前目录/祖先目录均扫描），
    该位置 DSH 也扫描（project-agents 根），所以一处安装两边生效。
    """
    if user_level and harness == "codex":
        return Path.home() / ".agents" / "skills"
    if user_level and harness == "dsh":
        return Path(os.environ.get("DSH_HOME", Path.home() / ".dsh")) / "skills"
    relative = {"qoder": Path(".qoder/skills"), "dsh": Path(".dsh/skills"),
                "codex": Path(".agents/skills")}[harness]
    return root / relative


def cmd_install(root, args):
    plugin = Path(__file__).resolve().parent.parent
    skills_src = plugin / "skills"
    harness = args.harness

    if harness == "none":
        pass
    elif harness == "qoder" and not (root / ".qoder").exists():
        print("目标项目没有 .qoder 目录，跳过 skill 安装（runner 仍可用）")
    else:
        base = skill_root(root, harness, args.user_level)
        for skill_dir in sorted(skills_src.iterdir()):
            if not skill_dir.is_dir():
                continue
            destination = base / skill_dir.name
            for source in skill_dir.rglob("*"):
                if source.is_dir():
                    continue
                target = destination / source.relative_to(skill_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            print(f"  + {destination}")

    state = state_dir(root)
    state.mkdir(parents=True, exist_ok=True)
    for name in ("devguard.py",):
        shutil.copyfile(plugin / "runner" / name, state / name)
    load_policy(root, create=True)
    excluded = ensure_excluded(root)

    print(f"已安装到 {root}")
    print(f"  入口：python -I {STATE_DIR}/devguard.py check")
    if excluded:
        print(f"  {STATE_DIR}/ 已加入 .git/info/exclude")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="SRM DevGuard")
    parser.add_argument("--root", default=None, help="SRM 仓库根（默认当前目录或向上查找）")
    parser.add_argument("--state", default=None,
                        help="状态目录（默认 <root>/.archguard；外置即只读运行，不写仓库）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="冻结现状并生成策略文件")

    check = sub.add_parser("check", help="交付前自检（只报新增）")
    check.add_argument("--base", default="HEAD", help="对比基线（默认 HEAD）")
    check.add_argument("--strict-budget", action="store_true", help="范围预算超限即阻断")

    audit = sub.add_parser("audit", help="旧代码改造候选")
    audit.add_argument("--top", type=int, default=None)
    audit.add_argument("--since", default=None, help="热度窗口，如 180 days ago")
    audit.add_argument("--file", default=None, help="只看单个类（类名或相对路径）")
    audit.add_argument("--include-tests", action="store_true", help="把测试代码一并纳入排序")
    audit.add_argument("--json", action="store_true")

    review = sub.add_parser("review", help="设计文档机械预检（不代替人工评审）")
    review.add_argument("--doc", required=True, help="设计文档路径（.md）")
    review.add_argument("--code", default=None, help="核对代码事实的仓库根（默认同 --root）")
    review.add_argument("--roles", default=None, help="逗号分隔的角色码，如 CGY,CGZZ")
    review.add_argument("--strict-facts", action="store_true",
                        help="把“声称已存在但代码中没有”也算作阻断（默认仅提示）")
    review.add_argument("--json", action="store_true")

    feedback = sub.add_parser("feedback", help="记录这条提示有用/是噪声")
    feedback.add_argument("--key", required=True)
    feedback.add_argument("--verdict", required=True, choices=["useful", "noise", "false-positive"])
    feedback.add_argument("--note", default="")

    report = sub.add_parser("report", help="汇总运行记录与反馈")
    report.add_argument("--limit", type=int, default=10)

    install = sub.add_parser("install", help="装 skill 到 IDE，并初始化本地目录")
    install.add_argument("--harness", default="none", choices=["none", "qoder", "dsh", "codex"])
    install.add_argument("--user-level", action="store_true",
                         help="装到用户级目录（codex: ~/.agents/skills；dsh: $DSH_HOME/skills）")

    args = parser.parse_args(argv)

    global _STATE_ROOT
    _STATE_ROOT = args.state

    if args.root:
        root = Path(args.root).resolve()
    else:
        root = Path.cwd()
        while not (root / "srm-server").is_dir() and root.parent != root:
            root = root.parent
    if not root.is_dir():
        print(f"找不到 SRM 仓库根：{root}", file=sys.stderr)
        return 2

    handlers = {"init": cmd_init, "check": cmd_check, "audit": cmd_audit,
                "review": cmd_review, "feedback": cmd_feedback, "report": cmd_report,
                "install": cmd_install}
    return handlers[args.command](root, args)


if __name__ == "__main__":
    sys.exit(main())
