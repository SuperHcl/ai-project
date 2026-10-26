#!/usr/bin/env python3
"""ArchGuard 安装器：把同一套 SKILL 与规则安装到 Qoder / Codex / DSH。

三者差异（已按各自实测约定实现）：
  Qoder  <project>/.qoder/skills/<name>/SKILL.md  +  .qoder/rules/*.md（自动加载）
  DSH    <project>/.dsh/skills/<name>/SKILL.md     +  AGENTS.md（自动加载）
  Codex  <project>/.codex/prompts/<name>.md        +  AGENTS.md（Codex 无原生 Skill，
                                                       SKILL 摊平成 slash prompt）

用法（在插件目录执行，或 -File 方式调用 install.ps1）：
  python -I scripts/install.py --project d:\\workspaces\\ai\\srm --harness all
  python -I scripts/install.py --project . --harness qoder --dry-run
  python -I scripts/install.py --project . --harness dsh --user-level
  python -I scripts/install.py --project . --with-hook
  python -I scripts/install.py --self-check

幂等：内容一致不写盘；--force 才强制覆盖。只增删自己标记块内的内容。
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = PLUGIN_ROOT / "skills"
RULES_SRC = PLUGIN_ROOT / "rules" / "AGENT.md"
SCRIPTS = ("ratchet.py", "scan_design.py", "verify.py")
GUARD_DIR = ".arch-guard"
BLOCK_BEGIN = "<!-- arch-guard:begin -->"
BLOCK_END = "<!-- arch-guard:end -->"
HOOK_MARKER = "# ARCH_GUARD_HOOK_V1"

SKILL_TARGETS = {
    "qoder": Path(".qoder") / "skills",
    "dsh": Path(".dsh") / "skills",
    "codex": Path(".codex") / "prompts",
}


class InstallError(RuntimeError):
    pass


class WorkspaceTemp:
    """自检用临时目录。

    刻意不放在系统临时目录：受限环境（如 Windows 沙箱）常允许在 TEMP 下建根目录
    但拒绝在其中再建子目录，导致自检误报失败。改用插件目录下的 .selftest。
    """

    def __init__(self, parent):
        self.parent = parent
        self.path = None

    def __enter__(self):
        self.path = self.parent / ".selftest"
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        self.path.mkdir(parents=True)
        return str(self.path)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)
        return False



def read(path):
    return path.read_bytes()


def write_if_changed(target, payload, force, dry_run, log):
    """内容相同则跳过，保证幂等。"""
    exists = target.exists()
    if exists and not force and target.is_file():
        try:
            if read(target) == payload:
                log.append(f"[SKIP]    {target}")
                return False
        except OSError:
            pass
    if dry_run:
        log.append(("[OVERWRITE] " if exists else "[NEW]       ") + str(target))
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    log.append(("[UPDATE]  " if exists else "[NEW]       ") + str(target))
    return True


def copy_skill(src_dir, dst_dir, force, dry_run, log):
    for source in sorted(src_dir.rglob("*")):
        if source.is_dir():
            continue
        relative = source.relative_to(src_dir)
        write_if_changed(dst_dir / relative, read(source), force, dry_run, log)


def render_prompt(skill_dir):
    """Codex 无原生 Skill：把 SKILL.md 摊平成单文件 prompt，保留名称。"""
    body = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    name = skill_dir.name
    return f"<!-- arch-guard skill: {name} -->\n{body}".encode("utf-8")


def rules_block():
    return (BLOCK_BEGIN + "\n" + RULES_SRC.read_text(encoding="utf-8").rstrip()
            + "\n" + BLOCK_END + "\n")


def patch_agents(project, dry_run, log):
    """在 AGENTS.md 内维护一个标记块；块外内容一律不改。"""
    target = project / "AGENTS.md"
    block = rules_block()
    if not target.exists():
        payload = "# AGENTS\n\n" + block
        if dry_run:
            log.append(f"[NEW]       {target}（仅含 arch-guard 块）")
            return
        target.write_text(payload, encoding="utf-8")
        log.append(f"[NEW]       {target}（仅含 arch-guard 块）")
        return

    text = target.read_text(encoding="utf-8")
    begin = text.find(BLOCK_BEGIN)
    end = text.rfind(BLOCK_END)
    if begin != -1 and end > begin:
        candidate = text[:begin] + block.rstrip("\n") + text[end + len(BLOCK_END):]
    else:
        candidate = text.rstrip("\n") + "\n\n" + block

    if candidate == text:
        log.append(f"[SKIP]    {target}（arch-guard 块无变化）")
        return
    if dry_run:
        log.append(f"[UPDATE]  {target}（arch-guard 块）")
        return
    target.write_text(candidate, encoding="utf-8")
    log.append(f"[UPDATE]  {target}（arch-guard 块）")


def install_hook(project, dry_run, log):
    top = subprocess.run(["git", "-C", str(project), "rev-parse", "--show-toplevel"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         encoding="utf-8", errors="replace")
    if top.returncode != 0:
        raise InstallError(f"目标不是 Git 仓库，未安装 hook：{project}")
    actual = Path(top.stdout.strip()).resolve()
    if actual != project.resolve():
        raise InstallError(f"目标不是独立 Git 仓库根（实际根：{actual}），拒绝安装 hook")
    git_dir = subprocess.run(["git", "-C", str(project), "rev-parse", "--path-format=absolute",
                              "--git-path", "hooks"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
    if git_dir.returncode != 0:
        raise InstallError(f"目标不是 Git 仓库，未安装 hook：{project}")
    hook = Path(git_dir.stdout.strip()) / "pre-commit"
    entry = (
        "#!/bin/sh\n" + HOOK_MARKER + "\n"
        "# 由 ArchGuard 安装；只读当前检出，不联网、不改文件。\n"
        "repo=$(git rev-parse --show-toplevel) || exit 1\n"
        'guard="$repo/' + GUARD_DIR + '/verify.py"\n'
        'if [ ! -f "$guard" ]; then echo "[ArchGuard] 缺少检查器：$guard" >&2; exit 1; fi\n'
        'exec "' + sys.executable.replace('"', '') + '" -I "$guard" --fast\n'
    ).encode("utf-8")
    if hook.exists() and not hook.read_text(encoding="utf-8", errors="replace").startswith(
            "#!/bin/sh\n" + HOOK_MARKER):
        raise InstallError(f"已存在非 ArchGuard 管理的 pre-commit，未覆盖：{hook}")
    write_if_changed(hook, entry, True, dry_run, log)
    if not dry_run:
        hook.chmod(0o755)


def self_check():
    failures = []

    def expect(condition, message):
        if not condition:
            failures.append(message)

    with WorkspaceTemp(PLUGIN_ROOT) as temporary:
        project = Path(temporary) / "含空格的 project"
        project.mkdir()
        # 必须是独立仓库根：否则 git rev-parse 会解析到外层仓库，hook 会装错位置
        subprocess.run(["git", "-c", "init.templateDir=", "init", "-q"],
                       cwd=str(project), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        (project / ".qoder").mkdir()
        (project / ".dsh").mkdir()
        (project / ".codex").mkdir()

        log = []
        install(project, ["qoder", "dsh", "codex"], force=False, dry_run=False,
                user_level=False, with_hook=False, log=log)
        expect((project / ".qoder" / "skills" / "archg-plan" / "SKILL.md").is_file(),
               "qoder skill 未落地")
        expect((project / ".dsh" / "skills" / "archg-boundary" / "SKILL.md").is_file(),
               "dsh skill 未落地")
        expect((project / ".codex" / "prompts" / "archg-budget.md").is_file(),
               "codex prompt 未落地")
        expect((project / ".qoder" / "rules" / "arch-guard.md").is_file(),
               "qoder 规则镜像未落地")
        expect((project / GUARD_DIR / "ratchet.py").is_file(), "检查器未落地")
        expect((project / "AGENTS.md").read_text(encoding="utf-8").count(BLOCK_BEGIN) == 1,
               "AGENTS.md 标记块数量不为 1")

        # 二次安装必须完全幂等：不产生任何 [NEW]/[UPDATE]
        second = []
        install(project, ["qoder", "dsh", "codex"], force=False, dry_run=False,
                user_level=False, with_hook=False, log=second)
        writes = [item for item in second if item.startswith(("[NEW]", "[UPDATE]", "[OVERWRITE]"))]
        expect(not writes, f"二次安装不幂等：{writes[:3]}")

        # 标记块外内容必须保留
        agents = project / "AGENTS.md"
        agents.write_text("# 项目约定\n\n自有内容\n\n" + rules_block(), encoding="utf-8")
        log = []
        install(project, ["dsh"], force=False, dry_run=False,
                user_level=False, with_hook=False, log=log)
        text = agents.read_text(encoding="utf-8")
        expect("自有内容" in text and text.count(BLOCK_BEGIN) == 1, "标记块修补破坏了块外内容")

        # hook：外来 hook 必须拒绝覆盖
        hook = project / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 23\n", encoding="utf-8")
        try:
            install_hook(project, dry_run=False, log=[])
            failures.append("外来 pre-commit 未被拒绝")
        except InstallError:
            expect(hook.read_text(encoding="utf-8").endswith("exit 23\n"), "外来 hook 被改写")

        hook.unlink()
        install_hook(project, dry_run=False, log=[])
        expect(hook.read_text(encoding="utf-8").startswith("#!/bin/sh\n" + HOOK_MARKER), "hook 未安装")

    if failures:
        print("自检失败：", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print("自检通过：三 harness 落地、二次幂等、AGENTS 块外保留、外来 hook 拒绝覆盖。")
    return 0


def install(project, harnesses, force, dry_run, user_level, with_hook, log):
    # 1. 检查器与基线目录
    for name in SCRIPTS:
        write_if_changed(project / GUARD_DIR / name, read(PLUGIN_ROOT / "scripts" / name),
                         force, dry_run, log)

    # 2. 各 harness 的 skill 落地
    skill_dirs = sorted(path for path in SKILLS_SRC.iterdir() if path.is_dir())
    for harness in harnesses:
        for skill_dir in skill_dirs:
            if harness == "codex":
                payload = render_prompt(skill_dir)
                target = project / SKILL_TARGETS["codex"] / f"{skill_dir.name}.md"
                write_if_changed(target, payload, force, dry_run, log)
            else:
                base = project
                if user_level and harness == "dsh":
                    base = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
                copy_skill(skill_dir, base / SKILL_TARGETS[harness] / skill_dir.name,
                           force, dry_run, log)

    # 3. 规则显性化
    if "qoder" in harnesses and not user_level:
        write_if_changed(project / ".qoder" / "rules" / "arch-guard.md", read(RULES_SRC),
                         force, dry_run, log)
    if ("dsh" in harnesses or "codex" in harnesses) and not user_level:
        patch_agents(project, dry_run, log)

    if with_hook:
        install_hook(project, dry_run, log)


def detect(project):
    found = []
    if (project / ".qoder").is_dir():
        found.append("qoder")
    if (project / ".dsh").is_dir():
        found.append("dsh")
    if (project / ".codex").is_dir() or (Path.home() / ".codex").is_dir():
        found.append("codex")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description="ArchGuard 安装器（qoder/dsh/codex）")
    parser.add_argument("--project", default=".", help="目标项目根目录")
    parser.add_argument("--harness", default="auto",
                        choices=["auto", "all", "qoder", "dsh", "codex"], help="目标 harness")
    parser.add_argument("--dry-run", action="store_true", help="只打印不落盘")
    parser.add_argument("--force", action="store_true", help="强制覆盖")
    parser.add_argument("--user-level", action="store_true", help="装到用户级目录（dsh/codex）")
    parser.add_argument("--with-hook", action="store_true", help="安装 git pre-commit")
    parser.add_argument("--self-check", action="store_true", help="在临时目录自检")
    args = parser.parse_args(argv)

    if args.self_check:
        return self_check()

    project = Path(args.project).resolve()
    if not project.is_dir():
        print(f"目标项目不存在：{project}", file=sys.stderr)
        return 2

    if args.harness == "auto":
        harnesses = detect(project)
        if not harnesses:
            print("未探测到 .qoder / .dsh / .codex；请用 --harness 指定。", file=sys.stderr)
            return 2
    elif args.harness == "all":
        harnesses = ["qoder", "dsh", "codex"]
    else:
        harnesses = [args.harness]

    if args.user_level and "qoder" in harnesses:
        print("Qoder 只支持项目级安装；去掉 --user-level 或不要选 qoder。", file=sys.stderr)
        return 2

    log = []
    try:
        install(project, harnesses, args.force, args.dry_run, args.user_level,
                args.with_hook, log)
    except InstallError as error:
        print(f"安装失败：{error}", file=sys.stderr)
        return 1

    print(f"ArchGuard -> {project}  [{', '.join(harnesses)}]"
          + ("  [dry-run]" if args.dry_run else ""))
    for line in log:
        print("  " + line)
    changed = [line for line in log if line.startswith(("[NEW]", "[UPDATE]", "[OVERWRITE]"))]
    if log:
        print(f"  变更 {len(changed)} 个 / 跳过 {len(log) - len(changed)} 个")
    if not args.dry_run:
        print("\n下一步：")
        print(f"  1) python -I {GUARD_DIR}/ratchet.py --init     # 记录现状基线")
        print(f"  2) python -I {GUARD_DIR}/verify.py             # 交付前自检")
        if "qoder" in harnesses:
            print("  3) 重开 Qoder，问「按 ArchGuard 出方案」验证 skill 触发")
    return 0


if __name__ == "__main__":
    sys.exit(main())
