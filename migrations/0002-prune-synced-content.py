#!/usr/bin/env python3
"""
Remove the content the plugin now carries from a consumer repository's `.github/`.

  python migrations/0002-prune-synced-content.py --repo PATH            # dry run
  python migrations/0002-prune-synced-content.py --repo PATH --apply

WHY THIS MIGRATION EXISTS
-------------------------
Before v3.1 there was no delivery mechanism for skills, agents, prompts, contexts, hooks
and shared memory other than copying them into every repository that wanted them. That is
why `.github/agents/` and its siblings exist in older installs, and it is why an upgrade
used to mean one pull request per repository.

The plugin carries all of it now. What is left on disk is a stale copy — the worst kind,
because it looks authoritative and diverges silently: a repository whose `.github/skills/`
was synced eight months ago has skills that no longer match the ones the plugin loads, and
nothing in a session says which copy won. Deleting the duplicate is the point of this
migration.

WHY IT DEFAULTS TO A DRY RUN
-----------------------------
This is the only migration in the set that deletes files, and a deletion nobody previewed
is a deletion nobody consented to. The default prints the plan and changes nothing;
`--apply` performs it. `scripts/orchestrator.py upgrade` runs migrations without `--apply`
for exactly this reason: the upgrade shows you what pruning would do, and you run this one
by hand when you have read the list.

One consequence to know about rather than discover. `cmd_upgrade` records a migration in
`appliedMigrations` on any zero exit, and a dry run exits zero — so after an upgrade this
migration is marked applied even though it deleted nothing, and a later upgrade will skip
it. Running it by hand with `--apply` is therefore not optional follow-up work that the
tool will nag you about a second time; the printed plan is the only prompt you get.

THE OWNERSHIP RULE, RESTATED BECAUSE IT IS THE WHOLE FILE
----------------------------------------------------------
Only paths the manifest records as written BY US, with ownership "strong", and whose
current contents still hash to what we recorded, are removed. Everything else is named in
the output and left alone:

  - **weak ownership** (adopted by migration 0001) — we found the file at a path we would
    have used, but we never observed writing it. That is not evidence of authorship.
  - **modified since install** — the hash moved, so somebody edited it. Their edit may be
    the only copy of a local customisation.
  - **not in the manifest at all** — a foreign file. Never "clean up" a file you cannot
    prove you created.

On a repository back-filled by migration 0001 every path is weak, so this migration
deletes nothing at all. That is the designed outcome rather than a failure: the honest
consequence of not having recorded the writes is that a human has to authorise the
removal. The list and the command to do it are printed.

`.github/instructions/` is deliberately NOT in the prune set. A consumer repository keeps
its own instruction files there — that is precisely the collision that made the old
`.gitignore` block dangerous (see migration 0003) — and a directory too risky to ignore
wholesale is far too risky to delete wholesale.

WHY THE MANIFEST ENTRIES GO TOO
--------------------------------
Every removed path's entry is dropped from `operations`. `cmd_doctor` reports a recorded
`write` whose file is missing as a PROBLEM and prescribes `repair`, and `repair` cannot
restore a file that no longer exists anywhere except inside a plugin. Leaving the entries
behind would hand every upgraded repository a permanent list of unfixable problems.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _lib import read_json, utc_now, write_json  # noqa: E402

MIGRATION = "0002-prune-synced-content"
INSTALL_FILE = ".github/orchestrator-install.json"

# The directories the plugin now carries. Everything under one of these prefixes is a
# candidate; ownership decides whether it is actually removed.
PRUNE_PREFIXES = [
    ".github/agents/",
    ".github/prompts/",
    ".github/hooks/",
    ".github/skills/",
    ".github/contexts/",
    ".github/memory/shared/",
]


class MigrationError(RuntimeError):
    """Raised when the migration cannot finish. The runner stops the whole upgrade."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_state(repo: Path, options: dict | None = None) -> dict:
    return {
        "repo": repo,
        "install": read_json(repo / INSTALL_FILE),
        "options": options or {},
    }


def on_disk(repo: Path) -> list:
    """Every file currently sitting under a prune prefix, repo-relative and sorted."""
    found = []
    for prefix in PRUNE_PREFIXES:
        base = repo / prefix
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                found.append(path.relative_to(repo).as_posix())
    return found


def applies_to(state: dict) -> bool:
    """Applies when anything is still sitting under a prune prefix, owned or not — a
    foreign file there is not removable, but it is still worth reporting once."""
    if not isinstance(state.get("install"), dict):
        return False
    return bool(on_disk(state["repo"]))


def classify(state: dict) -> dict:
    """
    Split what is on disk into removable / kept, with a reason attached to every kept
    path. The reasons are the output of this migration even when nothing is deleted.
    """
    repo: Path = state["repo"]
    install: dict = state["install"]

    manifest = {}
    for operation in install.get("operations", []):
        path = operation.get("path")
        if path and operation.get("op") in ("write", "adopt"):
            manifest[path] = operation

    removable, kept = [], []
    for rel in on_disk(repo):
        operation = manifest.get(rel)
        if operation is None:
            kept.append((rel, "foreign — not recorded in the manifest"))
            continue
        if operation.get("op") == "adopt" or operation.get("ownership") != "strong":
            kept.append((rel, "weak ownership — the write was never observed"))
            continue
        recorded = operation.get("sha256")
        if not recorded:
            kept.append((rel, "strong ownership but no recorded hash — cannot confirm "
                              "the file is still the one we wrote"))
            continue
        try:
            if sha256_file(repo / rel) != recorded:
                kept.append((rel, "modified since install — the edit may be someone's work"))
                continue
        except OSError as exc:
            kept.append((rel, f"unreadable: {exc}"))
            continue
        removable.append(rel)
    return {"removable": removable, "kept": kept}


def prune_empty_directories(repo: Path) -> list:
    """
    Remove directories left empty by the deletions, deepest first. A directory that still
    holds anything — including a foreign file we just declined to delete — is untouched,
    so this can never remove something the ownership rule protected.

    Failures here are ignored on purpose. This runs after the files are gone and the
    manifest is updated; an empty directory that will not delete is untidy, and raising
    over it would report the whole migration as failed after it had already succeeded.
    """
    removed = []

    def try_remove(path: Path) -> None:
        try:
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
                removed.append(path.relative_to(repo).as_posix())
        except OSError:
            pass

    for prefix in PRUNE_PREFIXES:
        base = repo / prefix
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            try_remove(path)
        try_remove(base)
    return removed


def migrate(state: dict) -> dict:
    repo: Path = state["repo"]
    install: dict = state["install"]
    apply_changes = bool(state.get("options", {}).get("apply"))

    plan = classify(state)
    report = {
        "migration": MIGRATION,
        "status": "applied" if apply_changes else "dry-run",
        "removed": [],
        "kept": plan["kept"],
        "directoriesRemoved": [],
        "notes": [],
    }

    if not apply_changes:
        report["removable"] = plan["removable"]
        return report

    failures = []
    for rel in plan["removable"]:
        try:
            (repo / rel).unlink()
            report["removed"].append(rel)
        except OSError as exc:
            failures.append(f"{rel}: {exc}")

    if report["removed"]:
        removed = set(report["removed"])
        install["operations"] = [
            op for op in install.get("operations", [])
            if not (op.get("op") == "write" and op.get("path") in removed)
        ]
        install["lastValidatedAt"] = utc_now()
        try:
            write_json(repo / INSTALL_FILE, install)
        except OSError as exc:
            raise MigrationError(
                f"removed {len(report['removed'])} file(s) but could not update "
                f"{INSTALL_FILE}: {exc}. `doctor` will report those paths as missing "
                f"until the manifest is corrected by hand."
            ) from exc

    report["directoriesRemoved"] = prune_empty_directories(repo)

    if failures:
        raise MigrationError(
            f"{len(failures)} file(s) could not be removed: " + "; ".join(failures[:5])
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune content the plugin now carries")
    parser.add_argument("--repo", default=".", help="the consumer repository to migrate")
    parser.add_argument("--apply", action="store_true",
                        help="perform the deletions. Without it this prints the plan only.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    state = read_state(repo, {"apply": args.apply})

    if state["install"] is None:
        print(f"{MIGRATION}: no {INSTALL_FILE} in {repo}. Nothing to prune against.")
        return 0
    if not applies_to(state):
        print(f"{MIGRATION}: skipped — nothing under {', '.join(PRUNE_PREFIXES)}")
        return 0

    try:
        report = migrate(state)
    except MigrationError as exc:
        print(f"{MIGRATION}: FAILED — {exc}", file=sys.stderr)
        return 1

    if report["status"] == "dry-run":
        removable = report["removable"]
        print(f"{MIGRATION}: DRY RUN — nothing has changed.")
        print(f"  {len(removable)} file(s) would be removed (owned, unmodified):")
        for rel in removable[:20]:
            print(f"    - {rel}")
        if len(removable) > 20:
            print(f"    ... and {len(removable) - 20} more")
    else:
        print(f"{MIGRATION}: removed {len(report['removed'])} file(s) and "
              f"{len(report['directoriesRemoved'])} empty director(ies).")
        for rel in report["removed"][:20]:
            print(f"    - {rel}")
        if len(report["removed"]) > 20:
            print(f"    ... and {len(report['removed']) - 20} more")

    kept = report["kept"]
    if kept:
        print(f"\n  {len(kept)} path(s) LEFT ALONE:")
        for rel, reason in kept[:20]:
            print(f"    - {rel}  ({reason})")
        if len(kept) > 20:
            print(f"    ... and {len(kept) - 20} more")
        print("  These are not ours to delete. Review them and remove by hand if they are")
        print("  stale copies of what the plugin now carries.")

    if report["status"] == "dry-run":
        print("\n  Re-run with --apply to perform the removals above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
