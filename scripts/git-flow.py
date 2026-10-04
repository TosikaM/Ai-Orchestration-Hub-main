#!/usr/bin/env python3
"""
Git and pull-request orchestration — the half of the lifecycle that was missing.

  python scripts/git-flow.py status
  python scripts/git-flow.py branch --task "add ImpactInvestment to the donation form"
  python scripts/git-flow.py commit --message "..." [--all]
  python scripts/git-flow.py pr --title "..." --body-file <path> [--draft]
  python scripts/git-flow.py checks [--wait]

WHY THIS EXISTS
---------------
The pipeline ran analyze -> implement -> review -> test and then stopped at a working
tree. Everything after that — branch, commit, push, pull request, CI, merge — was a human
copying the agent's output into their own terminal. That is not a small omission: it is
the half of the lifecycle a developer actually experiences, and its absence is what makes
the difference between "Claude wrote some code" and "a change moved through our process".

EVERY OPERATION IS AUTONOMY-GATED, AND THE GATE IS NOT HERE
-----------------------------------------------------------
This script does not enforce the autonomy level. `hooks/runtime/handlers/autonomy-gate.js`
does, at the point the shell command is issued, because that is the only place enforcement
cannot be bypassed by calling something else. What this script does is FAIL EARLY and
explain, so an agent at level 3 gets a useful message here rather than an opaque denial
three commands later:

    branch, commit   level 2   local, reversible with git
    push             level 4   visible to colleagues
    pr create        level 4   enters somebody's review queue
    merge            level 5   NOT IMPLEMENTED HERE, deliberately — see below

MERGE IS ABSENT ON PURPOSE
--------------------------
There is no `merge` subcommand. Merging is the one action in this sequence with no
cheap undo and no reviewer between it and the default branch. It stays a human keystroke,
and the honest reason is not technical — a level-5 grant would make it possible. It is
that a system which can merge its own work has removed the last place a person was
required to look, and the value of the four human gates upstream depends on that place
still existing.

SAFETY PROPERTIES
-----------------
  - Never commits on the default branch. Refuses and tells you to branch first.
  - Never force-pushes. The destructive gate forbids it independently; this simply has
    no code path that would try.
  - Uses argv arrays, never a formatted shell string — a branch name with a quote in it
    is a different command otherwise.
  - Redaction-scans the commit message and PR body before they leave the machine. A PR
    body is published; a commit message is permanent.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, config, redact_scan, repo_slug  # noqa: E402

DEFAULT_BRANCHES = {"main", "master", "develop", "trunk"}
BRANCH_MAX = 60


def git(*args, cwd=None, check=False):
    """argv array only. A branch name or message with a quote in it must never become
    part of a shell string."""
    result = subprocess.run(
        ["git", *args], cwd=str(cwd or ROOT),
        capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result


def current_branch(repo: Path) -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).stdout.strip()


def is_repo(repo: Path) -> bool:
    return git("rev-parse", "--is-inside-work-tree", cwd=repo).returncode == 0


def autonomy_level() -> int | None:
    doc = config("policy.json", {}) or {}
    return ((doc.get("defaults") or {}).get("autonomy") or {}).get("level")


def require_level(needed: int, what: str) -> int | None:
    """Fail early with an explanation. The real enforcement is the autonomy-gate hook."""
    level = autonomy_level()
    if level is None or level >= needed:
        return None
    print(f"REFUSED: {what} requires autonomy level {needed}; this repository is at {level}.")
    print()
    print("  This is a limit on blast radius, not on effort — retrying will not clear it.")
    print("  Produce the artifact instead and hand it to a human:")
    print(f"    python scripts/git-flow.py {'pr --title ... --body-file ...' if needed >= 4 else 'commit'} --dry-run")
    print()
    print("  Raising the level is a recorded human decision:")
    print("    python scripts/policy.py autonomy")
    print('    python scripts/decision.py log --decision "raise autonomy to 4 for <repo>" --rationale "..."')
    return 1


def scan_or_die(field: str, text: str) -> int | None:
    """A commit message is permanent and a PR body is published. Scan before, not after."""
    try:
        findings = redact_scan(text)
    except RuntimeError as exc:
        print(f"REFUSED: redaction taxonomy unavailable ({exc}).")
        return 3
    high = [f for f in findings if f["tier"] == "HIGH"]
    if high:
        print(f"REFUSED: {field} contains {len(high)} HIGH-tier finding(s):")
        for f in high:
            print(f"  - {f['id']} at line {f['line']}  ({f['description']})")
        print("\n  A commit message is permanent and a pull-request body is published.")
        print("  Neither is a place to discover a credential afterwards.")
        return 3
    medium = [f for f in findings if f["tier"] == "MEDIUM"]
    if medium:
        print(f"  note: {len(medium)} MEDIUM finding(s) in {field} — "
              f"{', '.join(sorted({f['id'] for f in medium}))}")
    return None


def slugify(task: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", task.lower()).strip("-")
    return slug[:BRANCH_MAX].rstrip("-") or "change"


# ------------------------------------------------------------------ subcommands

def cmd_status(args) -> int:
    repo = Path(args.repo).resolve()
    if not is_repo(repo):
        print(f"{repo} is not a git repository.")
        return 1

    branch = current_branch(repo)
    porcelain = git("status", "--porcelain", cwd=repo).stdout.splitlines()
    staged = [l for l in porcelain if l[:1] not in (" ", "?")]
    unstaged = [l for l in porcelain if l[:1] == " "]
    untracked = [l for l in porcelain if l.startswith("??")]

    print(f"repo      {repo.name}")
    print(f"branch    {branch}" + ("   <- DEFAULT BRANCH; branch before committing"
                                    if branch in DEFAULT_BRANCHES else ""))
    print(f"autonomy  {autonomy_level()}")
    print(f"staged    {len(staged)}")
    print(f"unstaged  {len(unstaged)}")
    print(f"untracked {len(untracked)}")

    upstream = git("rev-parse", "--abbrev-ref", "@{u}", cwd=repo)
    if upstream.returncode == 0:
        ahead = git("rev-list", "--count", "@{u}..HEAD", cwd=repo).stdout.strip()
        print(f"upstream  {upstream.stdout.strip()} (ahead {ahead})")
    else:
        print("upstream  none — this branch has never been pushed")
    return 0


def cmd_branch(args) -> int:
    repo = Path(args.repo).resolve()
    if not is_repo(repo):
        print(f"{repo} is not a git repository.")
        return 1
    blocked = require_level(2, "creating a branch")
    if blocked:
        return blocked

    name = args.name or f"{args.prefix}/{slugify(args.task or 'change')}"
    existing = git("rev-parse", "--verify", name, cwd=repo)
    if existing.returncode == 0:
        print(f"branch '{name}' already exists — switching to it")
        result = git("checkout", name, cwd=repo)
    else:
        result = git("checkout", "-b", name, cwd=repo)
    if result.returncode != 0:
        print(result.stderr.strip())
        return 1
    print(f"on branch {name}")
    return 0


def cmd_commit(args) -> int:
    repo = Path(args.repo).resolve()
    if not is_repo(repo):
        print(f"{repo} is not a git repository.")
        return 1
    blocked = require_level(2, "committing")
    if blocked:
        return blocked

    branch = current_branch(repo)
    if branch in DEFAULT_BRANCHES:
        print(f"REFUSED: refusing to commit directly to '{branch}'.")
        print("  Branch first:  python scripts/git-flow.py branch --task \"<what you are doing>\"")
        print("  Committing to the default branch skips review entirely, which is the one")
        print("  step the whole pipeline exists to reach.")
        return 1

    blocked = scan_or_die("commit message", args.message)
    if blocked:
        return blocked

    if args.all:
        git("add", "-A", cwd=repo)
    staged = git("diff", "--cached", "--name-only", cwd=repo).stdout.split()
    if not staged:
        print("nothing staged. Stage files, or pass --all.")
        return 1

    if args.dry_run:
        print(f"[dry-run] would commit {len(staged)} file(s) on {branch}:")
        for f in staged[:20]:
            print(f"  {f}")
        return 0

    result = git("commit", "-m", args.message, cwd=repo)
    if result.returncode != 0:
        print(result.stdout.strip() or result.stderr.strip())
        return 1
    sha = git("rev-parse", "--short", "HEAD", cwd=repo).stdout.strip()
    print(f"committed {sha} on {branch} ({len(staged)} file(s))")
    return 0


def cmd_pr(args) -> int:
    repo = Path(args.repo).resolve()
    if not is_repo(repo):
        print(f"{repo} is not a git repository.")
        return 1
    blocked = require_level(4, "opening a pull request")
    if blocked:
        return blocked

    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else (args.body or "")
    blocked = scan_or_die("pull-request body", args.title + "\n" + body)
    if blocked:
        return blocked

    branch = current_branch(repo)
    if branch in DEFAULT_BRANCHES:
        print(f"REFUSED: cannot open a pull request from '{branch}'.")
        return 1

    if args.dry_run:
        print(f"[dry-run] would push {branch} and open a PR:\n")
        print(f"  title: {args.title}")
        print(f"  body:  {len(body)} chars")
        return 0

    push = git("push", "-u", "origin", branch, cwd=repo)
    if push.returncode != 0:
        print(push.stderr.strip())
        return 1
    print(f"pushed {branch}")

    if subprocess.run(["gh", "--version"], capture_output=True).returncode != 0:
        print("\n`gh` is not installed, so the pull request was not opened.")
        print("The branch is pushed. Open it in the browser, or install the GitHub CLI.")
        print("\n--- title ---")
        print(args.title)
        print("--- body ---")
        print(body)
        return 0

    cmd = ["gh", "pr", "create", "--title", args.title, "--body", body]
    if args.draft:
        cmd.append("--draft")
    result = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip())
        return 1
    print(result.stdout.strip())
    return 0


def cmd_checks(args) -> int:
    repo = Path(args.repo).resolve()
    if subprocess.run(["gh", "--version"], capture_output=True).returncode != 0:
        print("`gh` is not installed — cannot read CI status.")
        print("This reports NOT AVAILABLE rather than green: an unknown check state is")
        print("not a passing one, and release-engineering blocks on red or unknown CI.")
        return 1
    cmd = ["gh", "pr", "checks"]
    if args.wait:
        cmd.append("--watch")
    result = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Git and pull-request orchestration")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)

    p = sub.add_parser("branch")
    p.add_argument("--task"); p.add_argument("--name")
    p.add_argument("--prefix", default="feature")
    p.set_defaults(func=cmd_branch)

    p = sub.add_parser("commit")
    p.add_argument("--message", required=True)
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("pr")
    p.add_argument("--title", required=True)
    p.add_argument("--body"); p.add_argument("--body-file")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_pr)

    p = sub.add_parser("checks")
    p.add_argument("--wait", action="store_true")
    p.set_defaults(func=cmd_checks)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
