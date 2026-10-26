#!/usr/bin/env python3
"""ArchGuard 范围预算检查：把「一次交太多」变成可判定的失败。

每次改动都量四个数：文件数、新增行数、新增端点、新增表。
超过 .arch-guard/budget.json 的上限即返回 1，用于交付前自检或 CI。

用法：
  python -I scope_check.py --root .                     # 对比 HEAD（工作区改动）
  python -I scope_check.py --root . --base origin/main   # 对比分支基线
  python -I scope_check.py --root . --staged             # 只算已暂存
  python -I scope_check.py --root . --init               # 生成默认预算文件
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

DEFAULT_BUDGET = {
    "max_files": 40,
    "max_added_lines": 800,
    "max_new_endpoints": 5,
    "max_new_tables": 2,
}
BUDGET_REL = ".arch-guard/budget.json"
ENDPOINT_RE = re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping")
TABLE_RE = re.compile(r"@TableName|CREATE\s+TABLE", re.I)
# 只用真实来源计量：端点在服务端代码里，建表在建表脚本/实体里；文档提到这些词不算
ENDPOINT_EXTS = {".java", ".kt", ".ts", ".tsx", ".js"}
TABLE_EXTS = {".java", ".sql", ".xml"}


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode, result.stdout.decode("utf-8", "replace"), \
        result.stderr.decode("utf-8", "replace")


def load_budget(root, path):
    target = (root / path).resolve() if not Path(path).is_absolute() else Path(path)
    if not target.exists():
        return dict(DEFAULT_BUDGET), target, False
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"预算文件无法解析：{target}（{error}）")
    merged = dict(DEFAULT_BUDGET)
    merged.update({key: data[key] for key in DEFAULT_BUDGET if key in data})
    return merged, target, True


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArchGuard 范围预算检查")
    parser.add_argument("--root", default=".", help="仓库根")
    parser.add_argument("--base", default="HEAD", help="对比基线（默认 HEAD）")
    parser.add_argument("--staged", action="store_true", help="只统计已暂存改动")
    parser.add_argument("--budget", default=BUDGET_REL, help="预算文件")
    parser.add_argument("--init", action="store_true", help="写入默认预算文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"仓库根不存在：{root}", file=sys.stderr)
        return 2
    code, _, _ = git(root, "rev-parse", "--show-toplevel")
    if code != 0:
        print(f"目标不是 Git 仓库：{root}", file=sys.stderr)
        return 2

    budget, budget_path, existed = load_budget(root, args.budget)
    if args.init:
        budget_path.parent.mkdir(parents=True, exist_ok=True)
        budget_path.write_text(json.dumps(budget, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"已写入默认预算：{budget_path}")
        return 0

    diff_args = ["diff"]
    if args.staged:
        diff_args.append("--cached")
    else:
        diff_args.append(args.base)

    # 文件数与增删行
    code, numstat, error = git(root, *(diff_args + ["--numstat"]))
    if code != 0 and "unknown revision" in error:
        print(f"基线不可用：{args.base}（{error.strip()}）", file=sys.stderr)
        return 2
    files, added, deleted, biggest = 0, 0, 0, []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add, rem, path = parts
        if add == "-":  # 二进制
            continue
        files += 1
        added += int(add)
        deleted += int(rem)
        biggest.append((int(add), path))

    # 新增端点与表：只看新增行
    code, unified, _ = git(root, *(diff_args + ["-U0"]))
    new_endpoints = new_tables = 0
    current = ""
    for line in unified.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        suffix = Path(current).suffix.lower()
        if suffix in ENDPOINT_EXTS and ENDPOINT_RE.search(line):
            new_endpoints += 1
        if suffix in TABLE_EXTS and TABLE_RE.search(line):
            new_tables += 1

    code, added_files, _ = git(root, *(diff_args + ["--name-only", "--diff-filter=A"]))
    new_files = len([line for line in added_files.splitlines() if line.strip()])

    # 未跟踪文件不体现在 git diff 里，但 AI 新建的文件恰恰最需要计量
    code, untracked, _ = git(root, "ls-files", "--others", "--exclude-standard")
    for rel in untracked.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files += 1
        new_files += 1
        added += text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        suffix = path.suffix.lower()
        if suffix in ENDPOINT_EXTS:
            new_endpoints += len(ENDPOINT_RE.findall(text))
        if suffix in TABLE_EXTS:
            new_tables += len(TABLE_RE.findall(text))
        biggest.append((len(text.splitlines()), rel + "（新增）"))

    checks = [
        ("文件数", files, budget["max_files"]),
        ("新增行", added, budget["max_added_lines"]),
        ("新增端点", new_endpoints, budget["max_new_endpoints"]),
        ("新增表", new_tables, budget["max_new_tables"]),
    ]
    over = [(name, value, limit) for name, value, limit in checks if value > limit]

    payload = {"base": args.base, "staged": args.staged, "new_files": new_files,
               "metrics": {name: value for name, value, _ in checks},
               "limits": {name: limit for name, _, limit in checks},
               "over": [{"metric": n, "value": v, "limit": l} for n, v, l in over]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if over else 0

    print("# ArchGuard 范围预算\n")
    print(f"- 基线：{args.base}{'（已暂存）' if args.staged else ''}")
    print(f"- 预算文件：{budget_path if existed else '默认值（未找到预算文件）'}\n")
    print("| 指标 | 本次 | 上限 | 判定 |")
    print("|---|---|---|---|")
    for name, value, limit in checks:
        print(f"| {name} | {value} | {limit} | {'超限' if value > limit else 'OK'} |")
    print(f"\n- 其中新增文件：{new_files}；删除行：{deleted}")

    if biggest:
        print("\n改动最大的文件：")
        for count, path in sorted(biggest, reverse=True)[:5]:
            print(f"  +{count:<5} {path}")
        print()

    if over:
        print("[超限] 本次改动超出范围预算：")
        for name, value, limit in over:
            print(f"  - {name}：{value} > {limit}")
        print("\n处理方式：拆分本次改动，只保留能独立上线/独立评审的那一部分。")
        print("确认合理时，改 .arch-guard/budget.json 并说明理由，禁止直接跳过检查。")
        return 1

    print("[通过] 在范围预算内。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
