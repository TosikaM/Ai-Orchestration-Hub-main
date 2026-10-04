#!/usr/bin/env python3
"""
Back-fill the operations manifest for a repository connected before v3.1.

  python migrations/0001-add-writes-manifest.py --repo PATH

WHY THIS MIGRATION EXISTS
-------------------------
v3.1 made `.github/orchestrator-install.json` the record of what the orchestrator
actually did to a repository, because `doctor`, `repair` and above all `uninstall` are
only honest if something wrote down the operations they are supposed to verify or
reverse. A repository connected before that has no such record. The file it does have,
`.github/orchestrator-sync.json`, stored the hub repository, the branch, the overlay
profile and a `lastSync` timestamp. It recorded *that* a sync happened. It never
recorded *what* the sync wrote.

So the paths have to be reconstructed from the shape the old installer used — the seven
directories it created under `.github/` and the four files it dropped there. That
reconstruction is inference from a directory layout, not a record of an observed write,
and the rest of this file exists to keep that distinction from getting lost.

WEAK OWNERSHIP IS A STATEMENT OF EVIDENCE, NOT PESSIMISM
--------------------------------------------------------
Every path adopted here is recorded with `"ownership": "weak"`. Not one of them gets
"strong", however obviously ours it looks, because we did not observe writing it and
claiming otherwise would license a later `uninstall` to delete a file we never created.
A developer who hand-wrote `.github/contexts/dev.md` before the orchestrator arrived, or
who kept editing an agent file after it was copied in, has work sitting at a path our
installer would also have used. "Strong" is a claim that we put those bytes there.
Inference from a filename is not that claim.

The cost of the conservative reading is that some genuinely-ours files are never
auto-removed and a human has to delete them. The cost of the optimistic reading is
silent data loss during an uninstall. Those are not comparable, so the choice is not
close.

WHY THE OPERATION KIND IS `adopt` AND NOT `write`
--------------------------------------------------
`cmd_uninstall` in scripts/orchestrator.py treats every `write` entry as a deletion
candidate and only consults `sha256` to decide whether the file has been *modified*
since — it does not branch on `ownership`. An entry whose entire meaning is "we are not
sure we created this" must therefore not be shaped like the entry that authorises
deletion, or the field carrying the doubt would be decorative.

`adopt` is a distinct kind, and both existing consumers do the safe thing with an
operation kind they do not recognise: `uninstall` ignores it, so nothing is deleted;
`doctor` iterates `write` entries only, so nothing is falsely reported missing. Being
ignored is the correct default for an uncertain record.

The visible consequence, which is intended rather than a shortfall: migration 0002 will
delete nothing on a back-filled repository, because there is nothing in the manifest it
owns. It prints the paths and the command instead, and a human decides.

WHAT ELSE GETS RECORDED
-----------------------
Two side effects that a file listing would miss, and that uninstall must reverse:

  - the managed `.gitignore` block, if its markers are present;
  - `git update-index --skip-worktree` bits, read from git rather than guessed.

The install state file itself is deliberately NOT adopted. It is not managed through the
manifest — `uninstall` removes it directly as its own last act — and an entry pointing at
the file that contains the entry is a small circularity with no reader.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _lib import read_json, utc_now, write_json  # noqa: E402

MIGRATION = "0001-add-writes-manifest"
INSTALL_FILE = ".github/orchestrator-install.json"
LEGACY_SYNC_FILE = ".github/orchestrator-sync.json"

GITIGNORE_BEGIN_PREFIX = "# >>> AI Orchestrator"
GITIGNORE_END_PREFIX = "# <<< AI Orchestrator"

# The footprint the pre-v3.1 installer created. Directories first, then the individual
# files. This list is deliberately broad: the cost of adopting a path we did not write is
# one line in a manifest that says "weak", while the cost of missing one is a file nobody
# can account for at uninstall time.
LEGACY_DIRECTORIES = [
    ".github/agents",
    ".github/prompts",
    ".github/hooks",
    ".github/skills",
    ".github/contexts",
    ".github/instructions",
    ".github/memory/shared",
    ".github/config",
]
LEGACY_FILES = [
    ".github/orchestrator-context.md",
    LEGACY_SYNC_FILE,
]


class MigrationError(RuntimeError):
    """Raised when the migration cannot finish. The runner stops the whole upgrade."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_state(repo: Path, options: dict | None = None) -> dict:
    """
    Build the state the contract passes around: the repository, its parsed install
    record, and the options this run was given. See migrations/README.md for why the
    repository travels inside `state` rather than as a second parameter.
    """
    return {
        "repo": repo,
        "install": read_json(repo / INSTALL_FILE),
        "options": options or {},
    }


def applies_to(state: dict) -> bool:
    """
    Applies when there is an install record whose operations list accounts for no files
    at all. A v3.1 `connect-repo.ps1` always records at least the context-file write, so
    an empty file account means the record predates the manifest. Re-running after a
    successful pass is a no-op by the same test, which is what makes standalone runs safe.
    """
    install = state.get("install")
    if not isinstance(install, dict):
        return False
    operations = install.get("operations") or []
    return not any(op.get("op") in ("write", "adopt") for op in operations)


def enumerate_legacy_paths(repo: Path) -> list:
    """Every existing file under the legacy footprint, as repo-relative posix paths."""
    found = []
    for directory in LEGACY_DIRECTORIES:
        base = repo / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                found.append(path.relative_to(repo).as_posix())
    for name in LEGACY_FILES:
        if (repo / name).is_file():
            found.append(name)
    return found


def read_index_flags(repo: Path) -> tuple:
    """
    Returns (skip_worktree, assume_unchanged, error) — the first two as lists of
    repo-relative paths, the third as a reason when git could not be read at all.

    The error is returned rather than swallowed. An empty list means "git says no bits are
    set"; a failed call means "we do not know", and reporting the second as the first is
    how a migration ends up asserting a repository is clean because it never looked.

    `git ls-files -v` tags each entry: `S` means skip-worktree, and a lowercase tag means
    assume-unchanged. Those are two different bits set by two different flags, and reading
    either one as "the other" produces a report that is confidently wrong — so they are
    separated here and counted separately. `-z` is used because git otherwise C-quotes
    paths containing unusual characters, and a quoted path handed back to `update-index`
    is a path that does not exist.
    """
    result = subprocess.run(
        ["git", "ls-files", "-v", "-z", "--", ".github"],
        capture_output=True, cwd=str(repo),
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        return [], [], (detail[-1] if detail else "git ls-files failed with no message")
    skip, assume = [], []
    for record in result.stdout.decode("utf-8", "replace").split("\0"):
        if len(record) < 3 or record[1] != " ":
            continue
        tag, path = record[0], record[2:]
        if tag == "S":
            skip.append(path)
        elif tag.islower():
            assume.append(path)
    return sorted(skip), sorted(assume), None


def migrate(state: dict) -> dict:
    repo: Path = state["repo"]
    install: dict = state["install"]
    report = {
        "migration": MIGRATION,
        "status": "applied",
        "adopted": [],
        "sideEffects": [],
        "notes": [],
    }

    paths = enumerate_legacy_paths(repo)
    operations = install.setdefault("operations", [])
    stamped = utc_now()

    for rel in paths:
        try:
            observed = sha256_file(repo / rel)
        except OSError as exc:
            # A path we cannot read is a path we cannot describe. Say so and move on
            # rather than recording an entry with a hole in it.
            report["notes"].append(f"could not hash {rel}: {exc}")
            continue
        operations.append({
            "op": "adopt",
            "path": rel,
            "ownership": "weak",
            "observedSha256": observed,
            "observedAt": stamped,
            "reason": "present at a path the pre-v3.1 installer used; the write was never "
                      "recorded, so ownership is inferred and therefore weak",
            "backfilledBy": MIGRATION,
        })
        report["adopted"].append(rel)

    gitignore = repo / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        has_begin = any(line.strip().startswith(GITIGNORE_BEGIN_PREFIX) for line in lines)
        has_end = any(line.strip().startswith(GITIGNORE_END_PREFIX) for line in lines)
        already = any(op.get("op") == "gitignore-block" for op in operations)
        if has_begin and has_end and not already:
            operations.append({
                "op": "gitignore-block",
                "path": ".gitignore",
                "markerBegin": next(line.strip() for line in lines
                                    if line.strip().startswith(GITIGNORE_BEGIN_PREFIX)),
                "backfilledBy": MIGRATION,
            })
            report["sideEffects"].append("gitignore-block")
        elif has_begin != has_end:
            report["notes"].append(
                ".gitignore has one managed marker but not the other. Migration 0003 "
                "rewrites the block; it will report this rather than guess at the extent."
            )

    skip, assume, git_error = read_index_flags(repo)
    if git_error:
        report["notes"].append(
            f"could not read the git index ({git_error}), so no skip-worktree bits were "
            f"recorded. This is 'unknown', not 'none' — run migration 0004 to check."
        )
    if skip and not any(op.get("op") == "skip-worktree" for op in operations):
        operations.append({
            "op": "skip-worktree",
            "paths": skip,
            "ownership": "weak",
            "observedAt": stamped,
            "reason": "read from git rather than inferred — these bits are set now, "
                      "whoever set them",
            "backfilledBy": MIGRATION,
        })
        report["sideEffects"].append(f"skip-worktree ({len(skip)} path(s))")
    if assume:
        report["notes"].append(
            f"{len(assume)} path(s) under .github/ carry the assume-unchanged bit, which is "
            f"a different flag from skip-worktree and is not recorded here. Migration 0004 "
            f"clears both."
        )

    install["lastValidatedAt"] = stamped
    try:
        write_json(repo / INSTALL_FILE, install)
    except OSError as exc:
        raise MigrationError(f"could not write {INSTALL_FILE}: {exc}") from exc

    if not report["adopted"] and not report["sideEffects"]:
        report["status"] = "noop"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Back-fill the v3.1 operations manifest")
    parser.add_argument("--repo", default=".", help="the consumer repository to migrate")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    state = read_state(repo)

    if state["install"] is None:
        print(f"{MIGRATION}: no {INSTALL_FILE} in {repo}. Nothing to back-fill — this "
              f"repository is not connected.")
        return 0
    if not applies_to(state):
        print(f"{MIGRATION}: skipped — the manifest already accounts for files.")
        return 0

    try:
        report = migrate(state)
    except MigrationError as exc:
        print(f"{MIGRATION}: FAILED — {exc}", file=sys.stderr)
        return 1

    print(f"{MIGRATION}: adopted {len(report['adopted'])} path(s) as WEAK ownership.")
    for rel in report["adopted"][:20]:
        print(f"  adopt  {rel}")
    if len(report["adopted"]) > 20:
        print(f"  ... and {len(report['adopted']) - 20} more")
    for effect in report["sideEffects"]:
        print(f"  side effect recorded: {effect}")
    for note in report["notes"]:
        print(f"  note: {note}")
    if report["adopted"]:
        print("  Weak means uninstall will not delete these — we did not observe writing")
        print("  them. Removing them is a human decision; migration 0002 prints the list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
