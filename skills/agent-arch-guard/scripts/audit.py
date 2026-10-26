#!/usr/bin/env python3
"""ArchGuard 旧代码体检：按"复杂度 x 变更热度"排出改造候选，代替全量 review。

想法：5019 个文件不可能逐个看。真正值得改的是"又大又还在动"的那几十个；
又大但不动的先别碰，小而常动的不是结构问题。

用法：
  python -I audit.py --root <仓库根> --src srm-server/src/main/java
  python -I audit.py --src . --top 20 --json
  python -I audit.py --src . --since "180 days ago"
"""

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

EXCLUDE_DIRS = {
    ".git", "node_modules", "target", "build", "dist", "out", "bin", "obj",
    ".idea", ".vscode", ".gradle", ".arch-guard", "vendor", "__pycache__",
}
PUBLIC_METHOD_RE = re.compile(
    r"^\s{0,8}public\s+(?:static\s+|final\s+|synchronized\s+|abstract\s+|default\s+)*"
    r"[\w<>\[\],.?\s]+?\s+(\w+)\s*\(", re.M)
IMPORT_RE = re.compile(r"^\s*import\s+", re.M)
TODO_RE = re.compile(r"TODO|FIXME|暂不实现|待实现|未实现")
TYPE_DECL = re.compile(r"\b(class|interface|enum|record)\s+\w+")


def iter_java(src):
    for path in src.rglob("*.java"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        yield path


def count_lines(path):
    data = path.read_bytes()
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)


def churn_map(root, since):
    """统计窗口内每个文件被改动的次数。git 不可用或失败时返回空表。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "--pretty=format:", "--name-only", f"--since={since}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return {}
    if result.returncode != 0:
        return {}
    text = result.stdout.decode("utf-8", "replace")
    return Counter(line.strip() for line in text.splitlines() if line.strip())


def analyze(path, rel, churn):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = count_lines(path)
    methods = len([m for m in PUBLIC_METHOD_RE.finditer(text)
                   if not TYPE_DECL.search(m.group(0))])
    imports = len(IMPORT_RE.findall(text))
    todos = len(TODO_RE.findall(text))
    changes = churn.get(rel, 0)

    complexity = lines / 200.0 + methods / 10.0 + imports / 20.0
    score = complexity * (1.0 + math.log1p(changes))

    tags = []
    if lines >= 800:
        tags.append("巨型")
    elif lines >= 400:
        tags.append("偏大")
    if methods >= 40:
        tags.append("接口面大")
    if imports >= 60:
        tags.append("依赖过多")
    if changes >= 10:
        tags.append("高频改动")
    if todos:
        tags.append(f"TODOx{todos}")

    return {"file": rel, "lines": lines, "public_methods": methods, "imports": imports,
            "todos": todos, "changes": changes, "score": round(score, 1), "tags": tags}


def suggest(item):
    """给一个可执行的改造方向，而不是"建议优化"。"""
    if "巨型" in item["tags"] and "高频改动" in item["tags"]:
        return "最高优先：先按职责切成 2-3 个类，每次只搬一组方法，行为不变"
    if "巨型" in item["tags"]:
        return "暂缓：只在大改时才动它；改造前先明确它负责什么、不负责什么"
    if "接口面大" in item["tags"]:
        return "按调用方拆接口（读/写、内/外），不要按方法名拆"
    if "依赖过多" in item["tags"]:
        return "抽出协作对象：把 import 最多的那几个依赖收进一个门面类"
    if "高频改动" in item["tags"]:
        return "稳定但常动：检查是否缺一层，而不是继续加分支"
    return "按需处理"


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArchGuard 旧代码体检")
    parser.add_argument("--root", default=".", help="仓库根（用于 git 热度统计）")
    parser.add_argument("--src", action="append", required=True, help="源码根，可重复")
    parser.add_argument("--since", default="90 days ago", help="热度统计窗口")
    parser.add_argument("--top", type=int, default=15, help="展示条数")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    churn = churn_map(root, args.since)
    items = []
    for src_arg in args.src:
        src = Path(src_arg).resolve()
        if not src.exists():
            print(f"源码根不存在：{src}", file=sys.stderr)
            return 2
        for path in iter_java(src):
            rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
            item = analyze(path, rel, churn)
            if item:
                items.append(item)

    items.sort(key=lambda x: -x["score"])
    total_changes = sum(churn.values()) if churn else 0

    if args.json:
        print(json.dumps({"scanned": len(items), "churn_window": args.since,
                          "churn_total": total_changes, "top": items[: args.top]},
                         ensure_ascii=False, indent=2))
        return 0

    print("# ArchGuard 旧代码体检\n")
    print(f"- 扫描文件：{len(items)}")
    print(f"- 热度窗口：{args.since}（窗口内改动记录 {total_changes} 条）")
    print("- 排序依据：复杂度（行数/公开方法/依赖）x 变更热度；只改「又大又还在动」的\n")

    print("| # | 文件 | 行 | 公开方法 | 改动 | 标签 | 分数 |")
    print("|---|---|---|---|---|---|---|")
    for index, item in enumerate(items[: args.top], 1):
        print(f"| {index} | `{item['file']}` | {item['lines']} | {item['public_methods']} "
              f"| {item['changes']} | {' '.join(item['tags']) or '-'} | {item['score']} |")

    print("\n## 建议的改造顺序\n")
    for index, item in enumerate(items[: min(5, len(items))], 1):
        print(f"{index}. `{Path(item['file']).name}`：{suggest(item)}")

    hot = [item for item in items if "高频改动" in item["tags"]]
    print(f"\n> 本轮不做：{len(items) - len(hot)} 个文件不在近期改动范围，"
          f"除非本次需求正好要动它，否则不要顺手重构。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
