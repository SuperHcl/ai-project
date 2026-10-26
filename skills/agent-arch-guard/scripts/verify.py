#!/usr/bin/env python3
"""ArchGuard 统一校验入口：给 git pre-commit / CI / Agent 交付前自检使用。

判定口径（与 SKILL 一致）：
  1. 棘轮      —— 已知超大文件只许变小，新文件不许超上限（阻断）
  2. 范围预算  —— 文件数/新增行/新增端点/新增表（默认只报告，--scope-strict 才阻断）
  3. 设计扫描  —— 只报告不阻断（避免用噪声换绿灯）

用法：
  python -I .arch-guard/verify.py            # 全量
  python -I .arch-guard/verify.py --fast     # 只跑棘轮（pre-commit 用）
  python -I .arch-guard/verify.py --scope-strict
"""

import argparse
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent


def run(script, args):
    command = [sys.executable, "-I", str(HERE / script), *args]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.decode("utf-8", "replace")
    return result.returncode, output


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArchGuard 统一校验")
    parser.add_argument("--fast", action="store_true", help="只跑棘轮")
    parser.add_argument("--scope-strict", action="store_true", help="范围预算超限即失败")
    parser.add_argument("--json", action="store_true", help="透传 JSON 给扫描")
    parser.add_argument("--src", action="append", help="设计扫描的源码根（可重复）")
    args = parser.parse_args(argv)

    failed = False
    print("== 1/3 棘轮 ==")
    code, output = run("ratchet.py", ["--root", str(HERE.parent)])
    print(output.rstrip())
    if code not in (0, 2):
        failed = True
    if code == 2:
        print("（未初始化基线，跳过；执行 --init 后生效）")

    if args.fast:
        return 1 if failed else 0

    print("\n== 2/3 范围预算" + ("（阻断）" if args.scope_strict else "（只报告）") + " ==")
    code, output = run("scope_check.py", ["--root", str(HERE.parent)])
    print(output.rstrip())
    if args.scope_strict and code == 1:
        failed = True

    print("\n== 3/3 设计扫描（只报告） ==")
    roots = args.src or [str(HERE.parent)]
    scan_args = []
    for root in roots:
        scan_args.extend(["--src", root])
    if args.json:
        scan_args.append("--json")
    code, output = run("scan_design.py", scan_args)
    print(output.rstrip())

    if failed:
        print("\n[未通过] 见上方阻断项。")
        return 1
    print("\n[通过] 可交付。报告类结果请人工判断是否为真问题。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
