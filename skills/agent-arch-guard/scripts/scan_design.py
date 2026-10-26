#!/usr/bin/env python3
"""ArchGuard 设计扫描：找出过度设计、重复造轮子和超大文件的候选点。

只做静态正则级判断，不解析完整语法树；结论是"候选"，由人或 Agent 复核。
默认口径刻意保守：把项目既有的分层约定（XxxService / XxxServiceImpl）排除掉，
只报真正可疑的形状。噪声会让团队绕过门禁，比不报更糟。

用法：
  python -I scan_design.py --src <源码根>
  python -I scan_design.py --src <源码根> --json
  python -I scan_design.py --src <源码根> --strict      # 存在可疑单实现即失败
  python -I scan_design.py --src <源码根> --show-convention   # 连常规分层一起列出
"""

import argparse
import json
import re
import sys
from collections import defaultdict
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
INTERFACE_RE = re.compile(
    r"^\s*(?:public\s+|protected\s+|private\s+)?(?:static\s+)?(?:sealed\s+)?interface\s+(\w+)")
ABSTRACT_RE = re.compile(
    r"^\s*(?:public\s+|protected\s+|private\s+)?abstract\s+class\s+(\w+)")
IMPLEMENTS_RE = re.compile(r"\bimplements\s+([A-Za-z0-9_.,\s<>?]+?)(?:\s*\{|\s*$)")
EXTENDS_RE = re.compile(r"\bclass\s+\w+[^{]*\bextends\s+([A-Za-z0-9_.,\s<>?]+?)(?:\s*(?:implements|\{))")
SKIP_INTERFACE_NAMES = re.compile(r"(?:Test|Probe|Fixture|Constants?)$")

# 这些后缀在大型仓库里天然遍布各包，统计它们只会产生噪声
NOISE_SUFFIXES = {
    "Impl", "Config", "Configuration", "Constant", "Constants", "Handler", "Converter",
    "Entity", "Form", "Vo", "Dto", "Item", "Data", "File", "Message", "Job", "Client",
    "Adapter", "Document", "Mapper", "Dao", "Service", "ServiceImpl", "Controller",
    "Test", "Enum", "Exception", "Event", "Request", "Response", "Result", "Util",
    "Utils", "Helper", "Builder", "Context", "Field", "Column", "Properties",
}

# 真正值得怀疑"重复造轮子"的概念后缀（横切关注点）
CONCEPT_HINTS = {
    "Access", "Policy", "Guard", "Scope", "Permission", "Auth", "Rule", "Judgement",
    "Strategy", "Resolver", "Validator", "Interceptor", "Filter",
}


def iter_java(src):
    for path in src.rglob("*.java"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        yield path


def count_lines(path):
    data = path.read_bytes()
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)


def split_types(raw):
    cleaned = re.sub(r"<[^>]*>", "", raw)
    return [item.strip().split(".")[-1] for item in cleaned.split(",") if item.strip()]


def camel_suffix(name):
    words = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name)
    return words[-1] if len(words) > 1 else ""


def scan(src, god_lines, show_convention, concept_suffixes):
    interfaces = {}
    abstract = {}
    impl_count = defaultdict(set)
    sub_count = defaultdict(set)
    god_files = []
    suffix_groups = defaultdict(set)
    convention_count = 0

    for path in iter_java(src):
        rel = path.relative_to(src).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = count_lines(path)
        if lines >= god_lines:
            god_files.append((rel, lines))

        package = ""
        match = re.search(r"^\s*package\s+([\w.]+)\s*;", text, re.M)
        if match:
            package = match.group(1)

        for number, line in enumerate(text.splitlines(), 1):
            found = INTERFACE_RE.match(line)
            if found:
                interfaces[found.group(1)] = (rel, number)
                continue
            found = ABSTRACT_RE.match(line)
            if found:
                abstract[found.group(1)] = (rel, number)
                continue
            found = IMPLEMENTS_RE.search(line)
            if found:
                for name in split_types(found.group(1)):
                    impl_count[name].add(rel)
            if "class " in line:
                found = EXTENDS_RE.search(line)
                if found:
                    for name in split_types(found.group(1)):
                        sub_count[name].add(rel)

        for match in re.finditer(r"\bclass\s+(\w+)", text):
            suffix = camel_suffix(match.group(1))
            if suffix and package and suffix not in NOISE_SUFFIXES:
                suffix_groups[suffix].add(package)

    single_impl = []

    def consider(kind, name, rel, line, impls):
        nonlocal convention_count
        if SKIP_INTERFACE_NAMES.search(name):
            return
        if len(impls) != 1:
            return
        impl = next(iter(impls))
        # 项目既有分层约定：XxxService + XxxServiceImpl，不算过度设计
        if Path(impl).stem == name + "Impl":
            convention_count += 1
            if not show_convention:
                return
        single_impl.append({"type": kind, "name": name, "file": rel, "line": line, "impl": impl})

    for name, (rel, line) in sorted(interfaces.items()):
        consider("interface", name, rel, line, impl_count.get(name, set()))
    for name, (rel, line) in sorted(abstract.items()):
        consider("abstract", name, rel, line, sub_count.get(name, set()))

    duplicates = []
    for suffix, packages in sorted(suffix_groups.items()):
        if suffix not in concept_suffixes:
            continue
        if len(packages) >= 3:
            duplicates.append({"suffix": suffix, "packages": sorted(packages)})

    return {
        "single_implementation": single_impl,
        "god_files": [{"file": rel, "lines": lines}
                      for rel, lines in sorted(god_files, key=lambda x: -x[1])],
        "repeated_concepts": duplicates,
        "convention_interfaces": convention_count,
    }


def report(result, severity):
    single = result["single_implementation"]
    god = result["god_files"]
    repeated = result["repeated_concepts"]

    print("# ArchGuard 设计扫描\n")
    print(f"- 可疑单实现抽象：{len(single)}"
          f"（另有 {result['convention_interfaces']} 个 XxxService/XxxServiceImpl 分层约定，已跳过）")
    print(f"- 超大文件（>= {severity['god_lines']} 行）：{len(god)}")
    print(f"- 横切概念散落（同后缀 3+ 个包）：{len(repeated)}")

    if single:
        print("\n## 可疑单实现抽象（抽象预算候选：补第二个实现，或内联）")
        for item in single[: severity["limit"]]:
            print(f"- `{item['name']}` <- `{item['impl']}`  ({item['file']}:{item['line']})")
        if len(single) > severity["limit"]:
            print(f"- ... 其余 {len(single) - severity['limit']} 项省略（--json 查看全部）")

    if god:
        print("\n## 超大文件（棘轮 baseline 候选）")
        for item in god[: severity["limit"]]:
            print(f"- {item['lines']:>7} 行  `{item['file']}`")
        if len(god) > severity["limit"]:
            print(f"- ... 其余 {len(god) - severity['limit']} 项省略")

    if repeated:
        print("\n## 横切概念散落（疑似各写一份，收敛为组合子/注册表的候选）")
        for item in repeated:
            print(f"- `*{item['suffix']}` 出现在 {len(item['packages'])} 个包："
                  + ", ".join(item["packages"][:4])
                  + (" ..." if len(item["packages"]) > 4 else ""))

    if not (single or god or repeated):
        print("\n未发现候选问题。")


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArchGuard 设计扫描")
    parser.add_argument("--src", action="append", required=True, help="源码根，可重复")
    parser.add_argument("--god-lines", type=int, default=400, help="超大文件行数门槛")
    parser.add_argument("--limit", type=int, default=15, help="每类最多展示条数")
    parser.add_argument("--concept-suffix", action="append",
                        help="额外关注的概念后缀，如 --concept-suffix Export")
    parser.add_argument("--show-convention", action="store_true",
                        help="连 XxxService/XxxServiceImpl 一起列出")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="存在可疑单实现即返回 1")
    args = parser.parse_args(argv)

    roots = [Path(item).resolve() for item in args.src]
    for root in roots:
        if not root.exists():
            print(f"源码根不存在：{root}", file=sys.stderr)
            return 2

    suffixes = set(CONCEPT_HINTS)
    if args.concept_suffix:
        suffixes.update(args.concept_suffix)

    merged = {"single_implementation": [], "god_files": [], "repeated_concepts": [],
              "convention_interfaces": 0}
    for root in roots:
        result = scan(root, args.god_lines, args.show_convention, suffixes)
        for key in ("single_implementation", "god_files", "repeated_concepts"):
            merged[key].extend(result[key])
        merged["convention_interfaces"] += result["convention_interfaces"]

    severity = {"god_lines": args.god_lines, "limit": args.limit}
    if args.json:
        print(json.dumps(merged, ensure_ascii=False, indent=2))
    else:
        report(merged, severity)

    if args.strict and merged["single_implementation"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
