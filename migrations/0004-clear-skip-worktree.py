#!/usr/bin/env python3
"""
Clear `git update-index --skip-worktree` on paths the orchestrator no longer syncs.

  python migrations/0004-clear-skip-worktree.py --repo PATH
  python migrations/0004-clear-skip-worktree.py --repo PATH --dry-run

WHY THIS MIGRATION IS REQUIRED AND NOT OPTIONAL
------------------------------------------------
Skip-worktree is invisible state. It does not appear in `git status`, it is not in
`.gitignore`, it is not in any file in the repository, and it does not survive a fresh
clone — so a developer sees a bug that reproduces only on one machine, has nothing to
read that explains it, and no reason to suspect a bit exists at all. `git ls-files -v`
would tell them, but that only helps somebody who already knows what they are looking
for.

While the orchestrator was managing those files, setting the bit was a defensible trade:
it kept synced content out of `git status` in repositories where the files were already
tracked, and the install state recorded it so `uninstall` could reverse it. That trade
ends the moment we stop managing the file. What is left is a bit we set, on a file that is
now the repository's own, that hides the repository's own edits from the repository's own
tooling — with no record a person would ever encounter.

That is the worst kind of residue: a change to the developer's environment that outlives
the thing that made it and cannot be discovered by looking. So this migration applies by
default rather than proposing itself. `--dry-run` exists for inspection, but the asymmetry
justifies the default: clearing a bit that should not have been set costs nothing except
the file becoming visible again, while leaving one set costs an afternoon of somebody
debugging their own working tree.

TWO BITS, NOT ONE
-----------------
`git ls-files -v` tags skip-worktree entries `S` and assume-unchanged entries with a
lowercase letter. They are different bits, set by different flags, with the same practical
symptom, and both were reachable from the older tooling. A migration that clears one and
silently leaves the other has not reduced the residue — it has made what remains harder to
find, because the obvious explanation has already been ruled out. Both are cleared here,
with the flag each one actually requires.

SUBPROCESS SHAPE
----------------
Every git call is an argv ARRAY, never a formatted string: a repository is allowed to
contain a file named with a space or a shell metacharacter, and a string-built command
containing one is a different command. Paths are chunked at 100 per invocation because a
few hundred arguments exceeds the command-line limit with an error that names neither the
limit nor the cause.

When a chunk fails, it is retried one path at a time. `git update-index` aborts the whole
invocation on the first path it cannot mark — typically one that is no longer in the index
— so a single bad path in a batch of 100 would otherwise abandon the 99 good ones and
report nothing useful about which was which.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _lib import read_json, utc_now, write_json  # noqa: E402

MIGRATION = "0004-clear-skip-worktree"
INSTALL_FILE = ".github/orchestrator-install.json"
CHUNK = 100

# Still written and still managed under v3.1, so a skip-worktree bit on these two is
# current behaviour rather than residue. `uninstall` reverses them when the time comes.
STILL_MANAGED = {
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


def index_flags(repo: Path) -> tuple:
    """
    Returns (skip_worktree, assume_unchanged), each a sorted list of repo-relative paths.

    `-z` is used because git C-quotes paths containing unusual characters otherwise, and a
    quoted path handed back to `update-index` names a file that does not exist.
    """
    result = subprocess.run(
        ["git", "ls-files", "-v", "-z"],
        capture_output=True, cwd=str(repo),
    )
    if result.returncode != 0:
        raise MigrationError(
            "`git ls-files` failed — this does not look like a git repository, and the "
            "bits this migration clears only exist inside one."
        )
    skip, assume, tracked = [], [], set()
    for record in result.stdout.decode("utf-8", "replace").split("\0"):
        if len(record) < 3 or record[1] != " ":
            continue
        tag, path = record[0], record[2:]
        tracked.add(path)
        if tag == "S":
            skip.append(path)
        elif tag.islower():
            assume.append(path)
    return sorted(skip), sorted(assume), tracked


def recorded_paths(install: dict | None) -> set:
    paths = set()
    for operation in (install or {}).get("operations", []):
        if operation.get("op") == "skip-worktree":
            paths.update(operation.get("paths", []))
    return paths


def targets(state: dict) -> dict:
    """
    What to clear. The union of what git reports and what the install state recorded,
    minus the two paths still managed under v3.1.

    Both sources are needed. Git is authoritative about what is set right now, but a
    pre-v3.1 install recorded nothing at all, so on those repositories git is the only
    evidence there is; and a manifest that names a path git no longer tracks is still
    worth reading, because it tells us what to stop claiming.

    Recorded paths that have left the index are separated out rather than queued for
    clearing. A bit cannot be set on a path git does not track, so there is nothing there
    to clear, and treating "nothing to do" as a failure would stop the upgrade over a file
    somebody legitimately deleted.
    """
    skip, assume, tracked = index_flags(state["repo"])
    recorded = recorded_paths(state.get("install"))
    candidates = (set(skip) | recorded) - STILL_MANAGED
    return {
        "skipWorktree": sorted(candidates & tracked),
        "assumeUnchanged": sorted(set(assume) - STILL_MANAGED),
        "untracked": sorted(candidates - tracked),
        # Only bits that are actually set count as retained. A path the manifest names but
        # git does not flag is a stale claim, not a bit we chose to keep.
        "retained": sorted(set(skip) & STILL_MANAGED),
    }


def applies_to(state: dict) -> bool:
    """
    Applies when anything outside the still-managed pair carries either bit, and also when
    the manifest still claims a path git no longer tracks — that claim is wrong and
    `uninstall` would act on it.

    A failure to read the index propagates rather than being swallowed into "nothing to
    do". A migration that could not look cannot report that it found nothing.
    """
    plan = targets(state)
    return bool(plan["skipWorktree"] or plan["assumeUnchanged"] or plan["untracked"])


def clear(repo: Path, flag: str, paths: list) -> tuple:
    """
    Run `git update-index <flag>` over `paths`, chunked. Returns (cleared, failures).
    A failing chunk is retried path by path so one unmarkable file cannot take the other
    ninety-nine down with it.
    """
    cleared, failures = [], []
    for start in range(0, len(paths), CHUNK):
        chunk = paths[start:start + CHUNK]
        # argv array, never a formatted string.
        result = subprocess.run(
            ["git", "update-index", flag, "--", *chunk],
            capture_output=True, text=True, cwd=str(repo),
        )
        if result.returncode == 0:
            cleared.extend(chunk)
            continue
        for path in chunk:
            single = subprocess.run(
                ["git", "update-index", flag, "--", path],
                capture_output=True, text=True, cwd=str(repo),
            )
            if single.returncode == 0:
                cleared.append(path)
            else:
                detail = (single.stderr or "").strip().splitlines()
                failures.append((path, detail[-1] if detail else "git reported no reason"))
    return cleared, failures


def migrate(state: dict) -> dict:
    repo: Path = state["repo"]
    dry_run = bool(state.get("options", {}).get("dry_run"))
    plan = targets(state)

    report = {
        "migration": MIGRATION,
        "status": "dry-run" if dry_run else "applied",
        "skipWorktreeCleared": [],
        "assumeUnchangedCleared": [],
        "retained": plan["retained"],
        "failures": [],
        "planned": plan,
    }
    if dry_run:
        return report

    cleared, failures = clear(repo, "--no-skip-worktree", plan["skipWorktree"])
    report["skipWorktreeCleared"] = cleared
    report["failures"].extend(failures)

    cleared, failures = clear(repo, "--no-assume-unchanged", plan["assumeUnchanged"])
    report["assumeUnchangedCleared"] = cleared
    report["failures"].extend(failures)

    install = state.get("install")
    if isinstance(install, dict):
        # The manifest must now describe only what is still set, or `uninstall` will try
        # to reverse bits that are already gone and `doctor` will report drift that was
        # deliberate.
        operations = []
        for operation in install.get("operations", []):
            if operation.get("op") != "skip-worktree":
                operations.append(operation)
                continue
            remaining = [p for p in operation.get("paths", []) if p in STILL_MANAGED]
            if remaining:
                operations.append({**operation, "paths": remaining,
                                   "narrowedBy": MIGRATION, "narrowedAt": utc_now()})
        install["operations"] = operations
        install["lastValidatedAt"] = utc_now()
        try:
            write_json(repo / INSTALL_FILE, install)
        except OSError as exc:
            raise MigrationError(
                f"bits were cleared but {INSTALL_FILE} could not be updated: {exc}. "
                f"The manifest now over-states what is set; correct it by hand."
            ) from exc

    if report["failures"]:
        raise MigrationError(
            f"{len(report['failures'])} path(s) could not be cleared: "
            + "; ".join(f"{p}: {why}" for p, why in report["failures"][:5])
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear stale skip-worktree bits")
    parser.add_argument("--repo", default=".", help="the consumer repository to migrate")
    parser.add_argument("--dry-run", action="store_true",
                        help="list the bits that would be cleared and change nothing")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    state = read_state(repo, {"dry_run": args.dry_run})

    try:
        if not applies_to(state):
            print(f"{MIGRATION}: skipped — no stale skip-worktree or assume-unchanged bits.")
            return 0
        report = migrate(state)
    except MigrationError as exc:
        print(f"{MIGRATION}: FAILED — {exc}", file=sys.stderr)
        return 1

    if report["status"] == "dry-run":
        plan = report["planned"]
        print(f"{MIGRATION}: DRY RUN — nothing has changed.")
        print(f"  {len(plan['skipWorktree'])} skip-worktree bit(s) would be cleared")
        print(f"  {len(plan['assumeUnchanged'])} assume-unchanged bit(s) would be cleared")
        for path in (plan["skipWorktree"] + plan["assumeUnchanged"])[:20]:
            print(f"    - {path}")
        if plan["untracked"]:
            print(f"  {len(plan['untracked'])} recorded path(s) are no longer tracked — "
                  f"nothing to clear, the manifest entry is dropped instead.")
        print("  Re-run without --dry-run to clear them.")
        return 0

    print(f"{MIGRATION}: cleared {len(report['skipWorktreeCleared'])} skip-worktree bit(s) "
          f"and {len(report['assumeUnchangedCleared'])} assume-unchanged bit(s).")
    for path in (report["skipWorktreeCleared"] + report["assumeUnchangedCleared"])[:20]:
        print(f"    - {path}")
    total = len(report["skipWorktreeCleared"]) + len(report["assumeUnchangedCleared"])
    if total > 20:
        print(f"    ... and {total - 20} more")
    if report["planned"]["untracked"]:
        print(f"  {len(report['planned']['untracked'])} recorded path(s) are no longer in "
              f"the index; their manifest claim was dropped rather than acted on.")
    if report["retained"]:
        print(f"  {len(report['retained'])} bit(s) kept on paths still managed under v3.1:")
        for path in report["retained"]:
            print(f"    - {path}")
    if total:
        print("  These files are visible to git again. Expect them in the next `git status`;")
        print("  that is the bits being gone, not a change to the files themselves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
