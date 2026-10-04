#!/usr/bin/env python3
"""
The install lifecycle CLI.

  python scripts/orchestrator.py list-installed
  python scripts/orchestrator.py doctor [--repo PATH]
  python scripts/orchestrator.py repair [--repo PATH]
  python scripts/orchestrator.py upgrade [--repo PATH]
  python scripts/orchestrator.py uninstall --dry-run   (the documented first step)
  python scripts/orchestrator.py uninstall

WHY UNINSTALL IS THE SERIOUS ONE
---------------------------------
A tool that writes paths into a team's `.github/` and offers no removal path is a tool a
senior engineer is right to refuse. "Delete the files yourself" is not an uninstall when
the tool also edited `.gitignore` and ran `git update-index --skip-worktree` on tracked
files — that last one is invisible state a user cannot discover, let alone reverse,
without already knowing the flag exists.

So `operations` in `.github/orchestrator-install.json` records `gitignore-block` and
`skip-worktree` as first-class operations alongside file writes. Those two are exactly
what an uninstall must reverse and exactly what a file listing would miss.

THE OWNERSHIP RULE
------------------
This removes only what the install state records as written by us. A foreign file at a
path we would have used is named in the output and left alone. Never "clean up" a file
you cannot prove you created.

WHY DOCTOR EARNS ITS KEEP
--------------------------
Several readers in this system fall back to built-in defaults when their config file is
unreadable, and log the fallback somewhere nobody is looking. A repository whose
`config/` failed to sync is running on defaults, silently, forever. `doctor` is the only
thing that would ever say so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, budgets, hub_config, measure_discovery, read_json, utc_now, write_json  # noqa: E402

INSTALL_FILE = ".github/orchestrator-install.json"
GITIGNORE_BEGIN = "# >>> AI Orchestrator (auto-managed — do not edit) >>>"
GITIGNORE_END = "# <<< AI Orchestrator (auto-managed) <<<"

# Under the plugin model only two paths are written into a consumer repo. Everything
# else — agents, skills, prompts, contexts, hooks, shared memory — stays in the plugin.
# That is the single biggest simplification in this architecture: the managed gitignore
# block drops from ten paths to two, and the data-loss risk of writing into a repo that
# did not ask for it largely disappears.
MANAGED_PATHS = [
    ".github/orchestrator-context.md",
    ".github/orchestrator-install.json",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_state(repo: Path) -> dict | None:
    return read_json(repo / INSTALL_FILE)


def cmd_list_installed(args) -> int:
    repo = Path(args.repo).resolve()
    state = install_state(repo)
    if not state:
        print(f"No install state at {repo / INSTALL_FILE}.")
        print("This repository is not connected. Run /orchestrator-init, or scripts/connect-repo.ps1.")
        return 1
    print(f"{repo.name}")
    print(f"  hub          {state.get('hubRepository')} @ {state.get('hubVersion')}")
    print(f"  profile      {state.get('request', {}).get('profile')}")
    print(f"  overlay      {state.get('overlayProfile')}")
    print(f"  installed    {state.get('installedAt')}")
    print(f"  validated    {state.get('lastValidatedAt')}")
    print(f"\n  {len(state.get('operations', []))} recorded operation(s):")
    for operation in state.get("operations", []):
        kind = operation.get("op")
        if kind == "write":
            print(f"    write          {operation['path']}  ({operation.get('ownership','?')})")
        elif kind == "gitignore-block":
            print(f"    gitignore      {operation['path']}  managed block")
        elif kind == "skip-worktree":
            print(f"    skip-worktree  {', '.join(operation.get('paths', []))}")
        elif kind == "skip-foreign":
            print(f"    SKIPPED        {operation['path']}  ({operation.get('reason')})")
    return 0


def cmd_doctor(args) -> int:
    repo = Path(args.repo).resolve()
    problems = []
    notes = []

    state = install_state(repo)
    if not state:
        problems.append((
            f"no install state at {INSTALL_FILE}",
            "run /orchestrator-init in this repository, or scripts/connect-repo.ps1",
        ))
    else:
        for operation in state.get("operations", []):
            if operation.get("op") != "write":
                continue
            path = repo / operation["path"]
            if not path.exists():
                problems.append((f"missing: {operation['path']}",
                                 "python scripts/orchestrator.py repair"))
            elif operation.get("sha256") and sha256_file(path) != operation["sha256"]:
                notes.append(f"modified since install: {operation['path']} "
                             f"(a sync will back it up before replacing it)")

        gitignore = repo / ".gitignore"
        recorded_block = any(o.get("op") == "gitignore-block" for o in state.get("operations", []))
        if recorded_block:
            text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
            if GITIGNORE_BEGIN not in text or GITIGNORE_END not in text:
                problems.append(("the managed .gitignore block is missing or damaged",
                                 "python scripts/gitignore.py apply"))

        for operation in state.get("operations", []):
            if operation.get("op") != "skip-worktree":
                continue
            for rel in operation.get("paths", []):
                result = subprocess.run(
                    ["git", "ls-files", "-v", rel],
                    capture_output=True, text=True, cwd=str(repo),
                )
                if result.returncode == 0 and result.stdout and not result.stdout[0].islower():
                    notes.append(f"skip-worktree is NOT set on {rel} although install state "
                                 f"records it — invisible state has drifted")

        current_version = (hub_config().get("hub") or {}).get("version")
        if state.get("hubVersion") and current_version and state["hubVersion"] != current_version:
            problems.append((
                f"installed hub {state['hubVersion']}, current hub {current_version}",
                "python scripts/orchestrator.py upgrade",
            ))

    # The check that earns doctor its keep: a repo whose config failed to sync runs on
    # built-in defaults, silently and forever, and nothing else would ever say so.
    for name in ("token-budgets.json", "pipeline-graph.json", "stack-mappings.json",
                 "tool-registry.json", "redaction-patterns.json"):
        source = ROOT / "config" / name
        if not source.exists():
            problems.append((f"config/{name} missing from the hub",
                             "reinstall the plugin: /plugin marketplace update"))
        elif read_json(source) is None:
            problems.append((f"config/{name} is not valid JSON — readers will silently fall "
                             f"back to built-in defaults", f"fix or restore config/{name}"))

    total, _ = measure_discovery(ROOT)
    ceiling = budgets().get("discovery", {}).get("aggregateFrontmatterBytes", 4000)
    if isinstance(ceiling, int) and total > ceiling:
        problems.append((f"discovery footprint {total}B over the {ceiling}B ceiling",
                         "python scripts/context-bill.py --budget"))
    else:
        notes.append(f"discovery footprint {total}B / {ceiling}B")

    context_file = repo / ".github" / "orchestrator-context.md"
    if context_file.exists():
        age = (datetime.now(timezone.utc).timestamp() - context_file.stat().st_mtime) / 86400
        if age > 14:
            notes.append(f"orchestrator-context.md is {int(age)} days old (stale past 14) — "
                         f"treat its layer map as inferred rather than verified")

    print(f"Doctor — {repo}\n")
    for note in notes:
        print(f"  note     {note}")
    if not problems:
        print("\nINSTALL HEALTHY")
        return 0
    print()
    for problem, remedy in problems:
        print(f"  PROBLEM  {problem}")
        print(f"           fix: {remedy}")
    print(f"\n{len(problems)} problem(s).")
    return 1


def cmd_repair(args) -> int:
    repo = Path(args.repo).resolve()
    state = install_state(repo)
    if not state:
        print("No install state — nothing to repair from. Run /orchestrator-init first.")
        return 1
    request = state.get("request", {})
    print("Re-deriving the install from the recorded REQUEST rather than from what is on disk.")
    print(f"  profile {request.get('profile')} · with {request.get('with', [])} · "
          f"without {request.get('without', [])}")
    print("\nRepair regenerates the repo context file and re-applies the managed gitignore block.")
    print("It does not restore skills or agents — those live in the plugin, not here.")
    print("\nRun:")
    print(f"  python scripts/context-gen.py --repo {repo} --force")
    print(f"  python scripts/gitignore.py --repo {repo} apply")
    state["lastValidatedAt"] = utc_now()
    write_json(repo / INSTALL_FILE, state)
    return 0


def cmd_upgrade(args) -> int:
    repo = Path(args.repo).resolve()
    state = install_state(repo)
    if not state:
        print("No install state — nothing to upgrade.")
        return 1
    installed = state.get("hubVersion", "0.0.0")
    current = (hub_config().get("hub") or {}).get("version", "0.0.0")
    if installed == current:
        print(f"Already at {current}.")
        return 0

    migrations_dir = ROOT / "migrations"
    scripts = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]-*.py")) if migrations_dir.is_dir() else []
    print(f"Upgrading {installed} -> {current}")
    print(f"  {len(scripts)} migration(s) available\n")

    applied = state.setdefault("appliedMigrations", [])
    for script in scripts:
        if script.stem in applied:
            print(f"  [skip] {script.stem} (already applied)")
            continue
        print(f"  [run ] {script.stem}")
        result = subprocess.run(
            [sys.executable, str(script), "--repo", str(repo)],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            print(f"         {line}")
        if result.returncode != 0:
            print(f"         FAILED — stopping. Later migrations assume this one ran.")
            for line in result.stderr.splitlines()[-5:]:
                print(f"         {line}")
            write_json(repo / INSTALL_FILE, state)
            return 1
        applied.append(script.stem)

    state["hubVersion"] = current
    state["lastValidatedAt"] = utc_now()
    write_json(repo / INSTALL_FILE, state)
    print(f"\nUpgraded to {current}.")
    return 0


def cmd_uninstall(args) -> int:
    repo = Path(args.repo).resolve()
    state = install_state(repo)
    if not state:
        print("No install state — nothing recorded, so nothing to remove.")
        print("This command never removes a file it cannot prove it created.")
        return 1

    to_remove, foreign, side_effects = [], [], []
    for operation in state.get("operations", []):
        kind = operation.get("op")
        if kind == "write":
            path = repo / operation["path"]
            if not path.exists():
                continue
            if operation.get("sha256") and sha256_file(path) != operation["sha256"]:
                foreign.append((operation["path"], "modified since install"))
            else:
                to_remove.append(operation["path"])
        elif kind == "gitignore-block":
            side_effects.append(("gitignore-block", ".gitignore managed block"))
        elif kind == "skip-worktree":
            side_effects.append(("skip-worktree", ", ".join(operation.get("paths", []))))
        elif kind == "skip-foreign":
            foreign.append((operation["path"], operation.get("reason", "not written by us")))

    print(f"Uninstall plan for {repo}\n")
    print(f"  {len(to_remove)} file(s) to remove:")
    for path in to_remove:
        print(f"    - {path}")
    print(f"\n  {len(side_effects)} side effect(s) to reverse:")
    for kind, detail in side_effects:
        print(f"    - {kind}: {detail}")
    if foreign:
        print(f"\n  {len(foreign)} path(s) LEFT ALONE:")
        for path, reason in foreign:
            print(f"    - {path}  ({reason})")
        print("    These are not removed. A modified file may contain your work, and a file we")
        print("    did not write is not ours to delete.")

    if args.dry_run:
        print("\n--dry-run: nothing changed. Re-run without it to apply.")
        return 0

    for rel in to_remove:
        try:
            (repo / rel).unlink()
        except OSError as exc:
            print(f"  could not remove {rel}: {exc}")
    for kind, _ in side_effects:
        if kind == "gitignore-block":
            subprocess.run([sys.executable, str(ROOT / "scripts" / "gitignore.py"),
                            "--repo", str(repo), "remove"], check=False)
        elif kind == "skip-worktree":
            for operation in state.get("operations", []):
                if operation.get("op") == "skip-worktree":
                    for rel in operation.get("paths", []):
                        subprocess.run(["git", "update-index", "--no-skip-worktree", rel],
                                       cwd=str(repo), check=False)

    try:
        (repo / INSTALL_FILE).unlink()
    except OSError:
        pass
    print("\nUninstalled. The plugin itself is removed separately:")
    print("  /plugin uninstall orchestrator@algoworks")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrator install lifecycle")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-installed").set_defaults(func=cmd_list_installed)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("repair").set_defaults(func=cmd_repair)
    sub.add_parser("upgrade").set_defaults(func=cmd_upgrade)
    p = sub.add_parser("uninstall"); p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_uninstall)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
