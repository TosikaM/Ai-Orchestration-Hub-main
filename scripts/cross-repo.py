#!/usr/bin/env python3
"""
Cross-repo orchestration: the registry, groups, and the contract band.

  python scripts/cross-repo.py status
  python scripts/cross-repo.py list
  python scripts/cross-repo.py connect <path> [--role <role>] [--group <name>]
  python scripts/cross-repo.py switch <name>
  python scripts/cross-repo.py group <name> [--repos a,b,c]
  python scripts/cross-repo.py band start <pipelineId> --repos a,b,c --requirement "..."
  python scripts/cross-repo.py band show [<pipelineId>]
  python scripts/cross-repo.py band advance <pipelineId> --repo <name> \
      --changes f1,f2 --exposes "Type.Field: shape" --build green
  python scripts/cross-repo.py lock <repo> | unlock <repo>

STATE LIVES OUTSIDE ANY REPOSITORY
-----------------------------------
`~/.orchestrator/state/connected-repos.json`. Previously this was editor-scoped
`globalState`, which meant the answer to "which repo am I in" existed only inside one
process. Moving it to a file is a strict improvement: the same state is readable from a
terminal, from CI, and from the view plane, and nothing has to ask a running editor.

THE RULE THE BAND EXISTS FOR
-----------------------------
Upstream contracts must be consumed downstream AS NAMED. Renaming a field downstream
because it reads better locally produces four repositories that each compile and do not
talk to each other — the characteristic failure of multi-repo work, and always a naming
drift rather than a logic error. If a name is genuinely wrong, change it upstream and
re-advance the band. One extra pass; the only correct move.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, read_json, repo_slug, state_path, utc_now, write_json  # noqa: E402

SESSIONS = ROOT / "memory" / "sessions"
LOCK_MAX_AGE_SECONDS = 3600


def registry_path() -> Path:
    return state_path("state", "connected-repos.json")


def load_registry() -> dict:
    return read_json(registry_path(), {
        "version": 1, "repos": [], "groups": [], "active": None, "activeGroup": None,
    })


def save_registry(registry: dict) -> None:
    write_json(registry_path(), registry)


def detect_stack(path: Path) -> str:
    """Reuses the shared detection order so two components cannot disagree about a stack."""
    from _lib import config
    mappings = config("stack-mappings.json", {})
    stacks = {s["id"]: s for s in mappings.get("stacks", [])}
    for stack_id in mappings.get("detectionOrder", []):
        stack = stacks.get(stack_id)
        if not stack or not stack.get("indicators"):
            continue
        for indicator in stack["indicators"]:
            if "file" in indicator:
                pattern = indicator["file"]
                matches = list(path.glob(pattern)) or list(path.glob(f"**/{pattern}"))[:5]
                for match in matches:
                    if "contains" not in indicator:
                        return stack_id
                    try:
                        if indicator["contains"] in match.read_text(encoding="utf-8", errors="ignore"):
                            return stack_id
                    except OSError:
                        continue
            elif "directory" in indicator:
                if (path / indicator["directory"]).is_dir() or list(path.glob(f"**/{indicator['directory']}"))[:1]:
                    return stack_id
    return "unknown"


def band_path(pipeline_id: str) -> Path:
    return SESSIONS / f"{pipeline_id}.band.json"


# ------------------------------------------------------------------ commands

def cmd_status(args) -> int:
    registry = load_registry()
    print(f"active repo:  {registry.get('active') or '(none)'}")
    print(f"active group: {registry.get('activeGroup') or '(none)'}")
    print(f"connected:    {len(registry.get('repos', []))} repo(s)")
    print(f"registry:     {registry_path()}")

    bands = sorted(SESSIONS.glob("*.band.json")) if SESSIONS.is_dir() else []
    if bands:
        print(f"\nbands in flight: {len(bands)}")
        for path in bands:
            band = read_json(path, {})
            remaining = band.get("remainingRepos", [])
            done = len(band.get("completedRepos", []))
            print(f"  {path.stem.replace('.band', '')}: {done} done, "
                  f"next {remaining[0] if remaining else '(none)'}")
    if not registry.get("active"):
        print("\nNo active repo. Falling back to the workspace folder name: "
              f"{repo_slug(Path.cwd())}")
    return 0


def cmd_list(args) -> int:
    registry = load_registry()
    repos = registry.get("repos", [])
    if not repos:
        print("No connected repos. Register one with `cross-repo.py connect <path>`.")
        return 0
    print(f"{'name':<24}{'stack':<20}{'role':<18}{'status':<10}path")
    print("-" * 100)
    for repo in repos:
        mark = "*" if repo["name"] == registry.get("active") else " "
        print(f"{mark}{repo['name']:<23}{repo.get('techStack','?'):<20}"
              f"{repo.get('role','-'):<18}{repo.get('status','active'):<10}{repo['path']}")
    groups = registry.get("groups", [])
    if groups:
        print(f"\ngroups:")
        for group in groups:
            print(f"  {group['name']}: {' -> '.join(group.get('executionOrder', group.get('repos', [])))}")
    return 0


def cmd_connect(args) -> int:
    path = Path(args.path).resolve()
    if not path.is_dir():
        print(f"not a directory: {path}")
        return 1
    if not (path / ".git").exists():
        print(f"WARNING: {path} has no .git. Connecting a non-repository is how orphaned")
        print("         .github folders happen. Continuing, but check the path.")

    registry = load_registry()
    name = repo_slug(path)
    stack = detect_stack(path)
    existing = next((r for r in registry["repos"] if r["name"] == name), None)
    entry = {
        "name": name,
        "path": str(path),
        "techStack": stack,
        "role": args.role or "-",
        "connectedDate": existing["connectedDate"] if existing else utc_now(),
        "lastSync": utc_now(),
        "contextFile": str(path / ".github" / "orchestrator-context.md"),
        "status": "active",
    }
    if existing:
        registry["repos"] = [entry if r["name"] == name else r for r in registry["repos"]]
        print(f"Updated {name} ({stack})")
    else:
        registry["repos"].append(entry)
        print(f"Connected {name} ({stack})")

    if args.group:
        group = next((g for g in registry.setdefault("groups", []) if g["name"] == args.group), None)
        if group is None:
            group = {"name": args.group, "repos": [], "executionOrder": []}
            registry["groups"].append(group)
        if name not in group["repos"]:
            group["repos"].append(name)
            group["executionOrder"].append(name)
        print(f"  added to group '{args.group}' at position {len(group['executionOrder'])}")
        print("  Check the execution order: producers must come before consumers.")

    registry["active"] = name
    save_registry(registry)
    print(f"\nNext: run /orchestrator-init in that repo to generate its context file.")
    return 0


def cmd_switch(args) -> int:
    registry = load_registry()
    match = next((r for r in registry["repos"] if r["name"] == args.name), None)
    if not match:
        known = ", ".join(r["name"] for r in registry["repos"]) or "(none)"
        print(f"no connected repo named '{args.name}'. Known: {known}")
        return 1
    registry["active"] = args.name
    save_registry(registry)
    print(f"active repo: {args.name}  ({match.get('techStack')})  {match['path']}")
    return 0


def cmd_group(args) -> int:
    registry = load_registry()
    groups = registry.setdefault("groups", [])
    group = next((g for g in groups if g["name"] == args.name), None)
    if args.repos:
        members = [r.strip() for r in args.repos.split(",") if r.strip()]
        if group is None:
            group = {"name": args.name, "repos": members, "executionOrder": members}
            groups.append(group)
        else:
            group["repos"] = members
            group["executionOrder"] = members
        print(f"group '{args.name}': {' -> '.join(members)}")
        print("Execution order is dependency-first: producers before consumers.")
    elif group is None:
        print(f"no group '{args.name}'. Create it with --repos a,b,c")
        return 1
    registry["activeGroup"] = args.name
    save_registry(registry)
    print(f"active group: {args.name}")
    return 0


def cmd_band(args) -> int:
    if args.action == "start":
        repos = [r.strip() for r in (args.repos or "").split(",") if r.strip()]
        if not repos:
            print("--repos is required, dependency-first")
            return 2
        band = {
            "pipelineId": args.pipeline_id,
            "requirement": args.requirement or "",
            "executionOrder": repos,
            "completedRepos": [],
            "sharedContracts": {},
            "remainingRepos": list(repos),
            "pipelineState": "analyze",
            "startedAt": utc_now(),
        }
        write_json(band_path(args.pipeline_id), band)
        print(f"Band started for {args.pipeline_id}: {' -> '.join(repos)}")
        print(f"  {band_path(args.pipeline_id).relative_to(ROOT)}")
        return 0

    if args.action == "show":
        paths = ([band_path(args.pipeline_id)] if args.pipeline_id
                 else sorted(SESSIONS.glob("*.band.json")) if SESSIONS.is_dir() else [])
        if not paths or not paths[0].exists():
            print("no band found")
            return 1
        for path in paths:
            band = read_json(path, {})
            print(f"\n{band.get('pipelineId', path.stem)}  [{band.get('pipelineState')}]")
            print(f"  {band.get('requirement', '')[:100]}")
            print(f"  order: {' -> '.join(band.get('executionOrder', []))}")
            for done in band.get("completedRepos", []):
                print(f"    [x] {done['repo']:<20} build={done.get('buildStatus','?')}")
                for iface in done.get("exposedInterfaces", []):
                    print(f"          exposes: {iface}")
            for pending in band.get("remainingRepos", []):
                print(f"    [ ] {pending}")
            contracts = band.get("sharedContracts", {})
            if contracts:
                print("\n  Shared contracts — consume these AS NAMED downstream:")
                for key, value in contracts.items():
                    print(f"    {key}: {value}")
        return 0

    if args.action == "advance":
        path = band_path(args.pipeline_id)
        band = read_json(path)
        if band is None:
            print(f"no band for {args.pipeline_id}")
            return 1
        if args.build != "green":
            print(f"build is '{args.build}', not green. Not advancing.")
            print("Downstream work against a repo that does not build is worse than no work:")
            print("the contract it exposes has not actually been proven to exist.")
            return 1

        exposes = [e.strip() for e in (args.exposes or "").split(";") if e.strip()]
        entry = {
            "repo": args.repo,
            "changes": [c.strip() for c in (args.changes or "").split(",") if c.strip()],
            "exposedInterfaces": exposes,
            "buildStatus": args.build,
            "notes": args.notes or "",
            "completedAt": utc_now(),
        }
        band["completedRepos"].append(entry)
        band["remainingRepos"] = [r for r in band.get("remainingRepos", []) if r != args.repo]
        for iface in exposes:
            if ":" in iface:
                key, shape = iface.split(":", 1)
                band["sharedContracts"][key.strip()] = shape.strip()
            else:
                band["sharedContracts"][iface] = ""
        write_json(path, band)

        print(f"Band advanced past {args.repo}.")
        if band["remainingRepos"]:
            nxt = band["remainingRepos"][0]
            print(f"  next: {nxt}")
            print("\n  Contracts that MUST be consumed as named in the next repo:")
            for key, shape in band["sharedContracts"].items():
                print(f"    {key}: {shape}")
            print("\n  Renaming one of these locally because it reads better is how a band")
            print("  produces repositories that each compile and do not talk to each other.")
        else:
            print("  band complete — every repo in the order is done.")
            print("\n  Honest limit: the band tracked contracts and order. It did NOT verify")
            print("  that a downstream repo wired the contract to the right thing — that needs")
            print("  an integration test crossing the repos. Say so when you report this.")
        return 0

    print("band action must be start, show, or advance")
    return 2


def cmd_lock(args) -> int:
    lock_file = state_path("locks", f"{args.repo}.json")
    existing = read_json(lock_file)
    if existing and time.time() - existing.get("acquiredAtEpoch", 0) < LOCK_MAX_AGE_SECONDS:
        print(f"'{args.repo}' is locked by session {existing.get('sessionId')} "
              f"since {existing.get('acquiredAt')}.")
        print("Wait rather than forcing. Two sessions implementing the same contract twice")
        print("is the thing the lock exists to prevent.")
        return 1
    write_json(lock_file, {
        "repo": args.repo,
        "sessionId": args.session or "cli",
        "acquiredAt": utc_now(),
        "acquiredAtEpoch": time.time(),
    })
    print(f"locked {args.repo}")
    return 0


def cmd_unlock(args) -> int:
    lock_file = state_path("locks", f"{args.repo}.json")
    if lock_file.exists():
        lock_file.unlink()
        print(f"unlocked {args.repo}")
    else:
        print(f"{args.repo} was not locked")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-repo orchestration")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("list").set_defaults(func=cmd_list)

    p = sub.add_parser("connect")
    p.add_argument("path"); p.add_argument("--role"); p.add_argument("--group")
    p.set_defaults(func=cmd_connect)

    p = sub.add_parser("switch"); p.add_argument("name"); p.set_defaults(func=cmd_switch)

    p = sub.add_parser("group")
    p.add_argument("name"); p.add_argument("--repos")
    p.set_defaults(func=cmd_group)

    p = sub.add_parser("band")
    p.add_argument("action", choices=["start", "show", "advance"])
    p.add_argument("pipeline_id", nargs="?")
    p.add_argument("--repos"); p.add_argument("--requirement")
    p.add_argument("--repo"); p.add_argument("--changes"); p.add_argument("--exposes")
    p.add_argument("--build", default="green"); p.add_argument("--notes")
    p.set_defaults(func=cmd_band)

    p = sub.add_parser("lock"); p.add_argument("repo"); p.add_argument("--session")
    p.set_defaults(func=cmd_lock)
    p = sub.add_parser("unlock"); p.add_argument("repo"); p.set_defaults(func=cmd_unlock)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
