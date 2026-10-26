#!/usr/bin/env python3
"""ArchGuard 腐烂棘轮：对已知的超大文件只许变小，新文件超过上限即阻断。

用法（在仓库根执行）：
  python -I .arch-guard/ratchet.py --init          # 生成基线（记录现状，不判失败）
  python -I .arch-guard/ratchet.py                 # 校验（默认 --check）
  python -I .arch-guard/ratchet.py --update        # 收敛后刷新基线（只降不升）
  python -I .arch-guard/ratchet.py --force-raise   # 人工确认后允许抬高基线

设计意图：不要求任何人现在重构坏代码，只保证它不再变大。
退出码：0 通过 / 1 违规 / 2 用法或基线错误。
"""

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

BASELINE_VERSION = 1
DEFAULT_BASELINE = ".arch-guard/baseline.json"
DEFAULT_EXTS = ".java,.kt,.ts,.tsx,.js,.jsx,.py,.go,.cs,.vue,.sql"
EXCLUDE_DIRS = {
    ".git", "node_modules", "target", "build", "dist", "out", "bin", "obj",
    ".idea", ".vscode", ".gradle", ".mvn", ".arch-guard", "vendor", "__pycache__",
}
# 单文件行数上限：超过即视为结构性问题的候选
DEFAULT_TRACK = 800
DEFAULT_NEW_LIMIT = 600


def count_lines(path):
    """按字节数换行符计数；不假定编码，避免脏文件中断扫描。"""
    data = path.read_bytes()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def iter_files(root, exts):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in exts:
            yield path


def display(path, root):
    """基线可能被放到仓库外，relative_to 会失败，退回绝对路径。"""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def load_baseline(path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"基线无法解析：{path}（{error}）")
    if data.get("version") != BASELINE_VERSION:
        raise SystemExit(f"基线版本不支持：{data.get('version')}，请用 --init 重建")
    return data


def save_baseline(path, root, files):
    payload = {
        "version": BASELINE_VERSION,
        "note": "只许变小；抬高需 --force-raise 并人工确认",
        "files": {rel: files[rel] for rel in sorted(files)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(root, exts):
    result = {}
    for path in iter_files(root, exts):
        result[path.relative_to(root).as_posix()] = count_lines(path)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArchGuard 腐烂棘轮")
    parser.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE, help="基线文件（相对仓库根）")
    parser.add_argument("--exts", default=DEFAULT_EXTS, help="统计的扩展名，逗号分隔")
    parser.add_argument("--track", type=int, default=DEFAULT_TRACK, help="--init 时纳入基线的行数门槛")
    parser.add_argument("--new-limit", type=int, default=DEFAULT_NEW_LIMIT, help="新文件行数上限")
    parser.add_argument("--init", action="store_true", help="生成基线")
    parser.add_argument("--check", action="store_true", help="校验（默认动作）")
    parser.add_argument("--update", action="store_true", help="下降后刷新基线")
    parser.add_argument("--force-raise", action="store_true", help="允许抬高基线（需人工确认）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"仓库根不存在：{root}", file=sys.stderr)
        return 2
    baseline_path = (root / args.baseline).resolve()
    exts = {item.strip().lower() for item in args.exts.split(",") if item.strip()}

    current = collect(root, exts)
    baseline = load_baseline(baseline_path)

    if args.init:
        tracked = {rel: lines for rel, lines in current.items() if lines >= args.track}
        save_baseline(baseline_path, root, tracked)
        biggest = sorted(tracked.items(), key=lambda item: item[1], reverse=True)[:5]
        print(f"已生成基线：{display(baseline_path, root)}")
        print(f"纳入 {len(tracked)} 个文件（>= {args.track} 行），合计扫描 {len(current)} 个文件")
        for rel, lines in biggest:
            print(f"  {lines:>7}  {rel}")
        print("提示：基线只允许变小。收敛后用 --update 刷新。")
        return 0

    if baseline is None:
        print(f"未找到基线：{baseline_path}", file=sys.stderr)
        print("先执行 --init 记录现状。", file=sys.stderr)
        return 2

    recorded = baseline["files"]
    violations, improvements, removals = [], [], []

    for rel, lines in sorted(current.items()):
        if rel in recorded:
            old = recorded[rel]
            if lines > old:
                violations.append(f"{rel}：{old} → {lines} 行（+{lines - old}）")
            elif lines < old:
                improvements.append(f"{rel}：{old} → {lines} 行")
        elif lines >= args.new_limit:
            violations.append(f"{rel}：新增 {lines} 行，超过新文件上限 {args.new_limit}")

    for rel in recorded:
        if rel not in current:
            removals.append(rel)

    if args.update:
        merged = dict(recorded)
        raised = []
        for rel, lines in current.items():
            if rel in merged:
                if lines < merged[rel]:
                    merged[rel] = lines
                elif lines > merged[rel]:
                    if args.force_raise:
                        raised.append(f"{rel}：{merged[rel]} → {lines}")
                        merged[rel] = lines
                    else:
                        continue
            elif lines >= args.track:
                merged[rel] = lines
        for rel in removals:
            merged.pop(rel, None)
        save_baseline(baseline_path, root, merged)
        print(f"基线已更新：{display(baseline_path, root)}")
        if improvements:
            print(f"  收紧 {len(improvements)} 个文件")
        if removals:
            print(f"  移除 {len(removals)} 个已删除文件")
        if raised:
            print(f"  抬高 {len(raised)} 个文件（--force-raise）")
            for item in raised:
                print(f"    {item}")
        if not violations:
            return 0

    if improvements or removals:
        print()
    if improvements:
        print(f"[改善] {len(improvements)} 个文件变小，可用 --update 收紧基线")
    if removals:
        print(f"[删除] {len(removals)} 个基线文件已不存在，可用 --update 清理")

    if violations:
        print(f"\n[阻断] {len(violations)} 项超出基线：")
        for item in violations:
            print(f"  - {item}")
        print("\n处理方式：拆分/下沉到更小的类；或确认是合理增长后人工执行 --update --force-raise。")
        return 1

    print(f"\n[通过] 基线内 {len(recorded)} 个文件均未变大。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
