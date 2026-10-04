#!/usr/bin/env python3
"""
Managed .gitignore block and skip-worktree handling.

  python scripts/gitignore.py apply   [--repo PATH]
  python scripts/gitignore.py remove  [--repo PATH]
  python scripts/gitignore.py status  [--repo PATH]

TWO PATHS, NOT TEN
------------------
Under the plugin distribution model only two files are written into a consumer
repository: the context file and the install state. Agents, skills, prompts, contexts,
hooks, and shared memory stay in the plugin, so they never need to be ignored.

That is worth noting because the previous shape ignored ten paths, and one of them was
the whole `.github/instructions/` directory — which would have swallowed a consumer
repo's own `copilot-instructions.md`. Silent data loss. The narrow list is not just
tidier; the class of bug goes away with it.

SUBPROCESS SAFETY
-----------------
`git update-index` is invoked with an argv ARRAY, never a formatted string, and the path
list is chunked at 100. A filename with a space in a string-built command is a different
command, and a few hundred paths exceeds the command-line limit with a confusing error.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BEGIN = "# >>> AI Orchestrator (auto-managed — do not edit) >>>"
END = "# <<< AI Orchestrator (auto-managed) <<<"
CHUNK = 100

MANAGED_PATHS = [
    ".github/orchestrator-context.md",
    ".github/orchestrator-install.json",
]

BLOCK_BODY = [
    BEGIN,
    "# Written by the AI Orchestrator and not intended for the consumer repo's history.",
    "# Remove this block with: python scripts/gitignore.py remove",
    *MANAGED_PATHS,
    END,
]


def read_lines(path: Path) -> list:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def strip_block(lines: list) -> list:
    out, inside = [], False
    for line in lines:
        if line.strip() == BEGIN:
            inside = True
            continue
        if line.strip() == END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return out


def cmd_apply(args) -> int:
    repo = Path(args.repo).resolve()
    gitignore = repo / ".gitignore"
    lines = strip_block(read_lines(gitignore))
    while lines and not lines[-1].strip():
        lines.pop()
    lines += ([""] if lines else []) + BLOCK_BODY + [""]
    gitignore.write_text("\n".join(lines), encoding="utf-8")
    print(f"Managed block applied to {gitignore}")
    for path in MANAGED_PATHS:
        print(f"  {path}")
    return 0


def cmd_remove(args) -> int:
    repo = Path(args.repo).resolve()
    gitignore = repo / ".gitignore"
    if not gitignore.exists():
        print("no .gitignore")
        return 0
    lines = read_lines(gitignore)
    stripped = strip_block(lines)
    if len(stripped) == len(lines):
        print("no managed block present")
        return 0
    while stripped and not stripped[-1].strip():
        stripped.pop()
    gitignore.write_text("\n".join(stripped) + "\n", encoding="utf-8")
    print(f"Managed block removed from {gitignore}. Everything else is untouched.")
    return 0


def cmd_status(args) -> int:
    repo = Path(args.repo).resolve()
    gitignore = repo / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    present = BEGIN in text and END in text
    print(f"{gitignore}: managed block {'present' if present else 'ABSENT'}")

    tracked = []
    for path in MANAGED_PATHS:
        result = subprocess.run(["git", "ls-files", "-v", path],
                                capture_output=True, text=True, cwd=str(repo))
        if result.returncode == 0 and result.stdout.strip():
            flag = result.stdout[0]
            state = "skip-worktree" if flag.islower() else "tracked"
            tracked.append(f"  {path}: {state}")
    if tracked:
        print("Tracked files:")
        print("\n".join(tracked))
        print("\nA tracked file cannot be ignored by .gitignore alone — that is what")
        print("skip-worktree is for, and it is invisible state, so it is recorded in")
        print(".github/orchestrator-install.json and reversed by uninstall.")
    return 0


def set_skip_worktree(repo: Path, paths: list, enable: bool) -> None:
    flag = "--skip-worktree" if enable else "--no-skip-worktree"
    for start in range(0, len(paths), CHUNK):
        chunk = paths[start:start + CHUNK]
        # argv array, never a formatted string.
        subprocess.run(["git", "update-index", flag, *chunk], cwd=str(repo), check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Managed .gitignore block")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply").set_defaults(func=cmd_apply)
    sub.add_parser("remove").set_defaults(func=cmd_remove)
    sub.add_parser("status").set_defaults(func=cmd_status)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
