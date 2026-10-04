#!/usr/bin/env python3
"""
Rewrite the managed `.gitignore` block from the old ten paths down to two.

  python migrations/0003-narrow-gitignore-block.py --repo PATH

WHY THIS MIGRATION EXISTS
-------------------------
Under the plugin model exactly two files are written into a consumer repository — the
generated context file and the install state — so the managed block has exactly two paths
to cover. The old block listed ten, because the old delivery mechanism copied agents,
prompts, hooks, skills, contexts and shared memory into `.github/` and then had to hide
all of it from `git status`.

Leaving the wide block in place is not merely untidy. Every path in it is a rule that
silently suppresses whatever grows there later, and the repository has no way to notice:
a file that is ignored does not appear in `git status`, so nothing ever prompts the
question.

THE BUG THIS REMOVES, AND WHY IT IS A CLASS AND NOT AN INSTANCE
---------------------------------------------------------------
One pass of the source block listed the whole `.github/instructions/` directory. That
directory is also where a consumer repository keeps its own `copilot-instructions.md`.
A developer writes it, commits nothing because `git status` is clean, and loses the file
to the next clean checkout. Silent data loss, caused by a rule nobody could see.

The narrow form fixes that instance. Narrowing to two *named files we actually write*
removes the class: a block that never ignores a directory cannot swallow a file that did
not exist when the block was written. That is the difference worth stating — the fix is
not "we corrected the instructions entry", it is "the block no longer contains the kind
of entry that can do this."

HOW THE REWRITE IS DONE
-----------------------
The old block is located by marker PREFIX rather than by exact string, because marker
text has changed over time and an exact match that misses leaves the old block in place
while the new one is appended below it — two managed blocks, one of them invisible to
every tool that looks for the current markers.

The new block is not written here. `scripts/gitignore.py apply` owns the block body, and
duplicating those lines in a migration guarantees the two disagree the first time one of
them changes. This migration strips the old block and then calls that script.

A block with an opening marker but no closing marker is REPORTED AND REFUSED, never
repaired by guessing where it ended. Guessing the extent of a delimiter-less region in a
file the user also edits means deleting the user's lines on a bad guess.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _lib import read_json, utc_now, write_json  # noqa: E402

MIGRATION = "0003-narrow-gitignore-block"
HUB_ROOT = Path(__file__).resolve().parent.parent
INSTALL_FILE = ".github/orchestrator-install.json"

BEGIN_PREFIX = "# >>> AI Orchestrator"
END_PREFIX = "# <<< AI Orchestrator"

# What the block is allowed to contain after this migration. Kept here only to decide
# whether the migration still applies — the block body itself comes from gitignore.py.
NARROW_PATHS = {
    ".github/orchestrator-context.md",
    ".github/orchestrator-install.json",
}


class MigrationError(RuntimeError):
    """Raised when the migration cannot finish. The runner stops the whole upgrade."""


def read_state(repo: Path, options: dict | None = None) -> dict:
    return {
        "repo": repo,
        "install": read_json(repo / INSTALL_FILE),
        "options": options or {},
    }


def find_block(lines: list) -> tuple:
    """
    Returns (begin_index, end_index) of the managed block, or (None, None) when there is
    none. Raises when a block opens and never closes — see the docstring.
    """
    begin = end = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if begin is None and stripped.startswith(BEGIN_PREFIX):
            begin = index
        elif begin is not None and stripped.startswith(END_PREFIX):
            end = index
            break
    if begin is not None and end is None:
        raise MigrationError(
            "the managed .gitignore block opens but never closes. Refusing to guess where "
            "it ends — a wrong guess deletes your own ignore rules. Add the closing marker "
            f"'{END_PREFIX} (auto-managed) <<<' where the block should end, then re-run."
        )
    return begin, end


def block_paths(lines: list, begin: int, end: int) -> list:
    """The non-comment, non-blank entries inside the block."""
    return [line.strip() for line in lines[begin + 1:end]
            if line.strip() and not line.strip().startswith("#")]


def applies_to(state: dict) -> bool:
    """
    Applies when a managed block exists and lists anything other than the two narrow
    paths. A block already narrowed is left alone, which makes a standalone re-run a
    no-op.
    """
    gitignore = state["repo"] / ".gitignore"
    if not gitignore.exists():
        return False
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    begin, end = find_block(lines)
    if begin is None:
        return False
    return set(block_paths(lines, begin, end)) != NARROW_PATHS


def unignored_by_removal(repo: Path, install: dict | None, removed: list) -> list:
    """
    For every directory entry the old block carried, list the files sitting there that the
    manifest does not claim. Those files were invisible to git and are visible again now,
    which is exactly the information a user needs in order to notice work they never
    committed.
    """
    owned = set()
    for operation in (install or {}).get("operations", []):
        if operation.get("op") in ("write", "adopt") and operation.get("path"):
            owned.add(operation["path"])

    surfaced = []
    for entry in removed:
        if not entry.endswith("/"):
            continue
        base = repo / entry.rstrip("/")
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(repo).as_posix()
                if rel not in owned:
                    surfaced.append(rel)
    return surfaced


def migrate(state: dict) -> dict:
    repo: Path = state["repo"]
    gitignore = repo / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    begin, end = find_block(lines)
    if begin is None:
        return {"migration": MIGRATION, "status": "noop", "removed": [], "surfaced": [],
                "notes": ["no managed block present"]}

    old_paths = block_paths(lines, begin, end)
    removed = [path for path in old_paths if path not in NARROW_PATHS]
    surfaced = unignored_by_removal(repo, state.get("install"), removed)

    # Strip the old block, keeping every line the user wrote around it, then let
    # gitignore.py append the canonical narrow block.
    kept = lines[:begin] + lines[end + 1:]
    while kept and not kept[-1].strip():
        kept.pop()
    gitignore.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(HUB_ROOT / "scripts" / "gitignore.py"), "apply",
         "--repo", str(repo)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise MigrationError(
            "the old block was removed but scripts/gitignore.py apply failed, so this "
            "repository currently has no managed block. Re-run "
            f"`python scripts/gitignore.py apply --repo {repo}` to restore it. "
            f"git-ignore reported: {result.stderr.strip()[:300]}"
        )

    install = state.get("install")
    if isinstance(install, dict):
        operations = install.setdefault("operations", [])
        existing = next((op for op in operations if op.get("op") == "gitignore-block"), None)
        if existing is None:
            operations.append({
                "op": "gitignore-block",
                "path": ".gitignore",
                "narrowedBy": MIGRATION,
                "narrowedAt": utc_now(),
            })
        else:
            existing["narrowedBy"] = MIGRATION
            existing["narrowedAt"] = utc_now()
        install["lastValidatedAt"] = utc_now()
        try:
            write_json(repo / INSTALL_FILE, install)
        except OSError as exc:
            raise MigrationError(f"could not update {INSTALL_FILE}: {exc}") from exc

    return {
        "migration": MIGRATION,
        "status": "applied",
        "removed": removed,
        "surfaced": surfaced,
        "notes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Narrow the managed .gitignore block")
    parser.add_argument("--repo", default=".", help="the consumer repository to migrate")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    state = read_state(repo)

    try:
        if not applies_to(state):
            print(f"{MIGRATION}: skipped — no managed block, or it is already narrow.")
            return 0
        report = migrate(state)
    except MigrationError as exc:
        print(f"{MIGRATION}: FAILED — {exc}", file=sys.stderr)
        return 1

    print(f"{MIGRATION}: block narrowed to {len(NARROW_PATHS)} path(s); "
          f"{len(report['removed'])} entr(ies) removed.")
    for entry in report["removed"]:
        print(f"    - {entry}")
    if report["surfaced"]:
        print(f"\n  {len(report['surfaced'])} file(s) are visible to git again. They were "
              f"covered by a directory entry above and never appeared in `git status`:")
        for rel in report["surfaced"][:20]:
            print(f"    - {rel}")
        if len(report["surfaced"]) > 20:
            print(f"    ... and {len(report['surfaced']) - 20} more")
        print("  Check whether any of these is your own work that was never committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
