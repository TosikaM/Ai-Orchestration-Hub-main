#!/usr/bin/env python3
"""
Cut a release: bump the version everywhere it appears, then prove nothing drifted.

  python scripts/release.py --version 3.2.0
  python scripts/release.py --bump minor
  python scripts/release.py --show

WHY A SCRIPT AND NOT A CHECKLIST
--------------------------------
The version lives in three files — hub.config.json, .claude-plugin/plugin.json and
.claude-plugin/marketplace.json — and a human bumping three files by hand gets two of
them right eventually. The failure is not loud: the marketplace resolves an install by
the version in the CATALOG while the plugin reports the version in its OWN manifest, so a
mismatch installs one thing and reports another. `orchestrator.py upgrade` then compares
the reported version against the installed one to decide whether migrations are due, so
drift here breaks the upgrade path rather than the install, which is the harder failure
to notice.

This bumps all three and then runs validate-structure.py. If the validator fails, the
version change is REVERTED rather than left half-applied — a repository sitting at a
version it cannot validate is worse than one that never bumped.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = {
    "hub.config.json": ("hub", "version"),
    ".claude-plugin/plugin.json": ("version",),
    ".claude-plugin/marketplace.json": ("plugins", 0, "version"),
}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def save(rel, data):
    (ROOT / rel).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def dig(data, path):
    for key in path:
        data = data[key]
    return data


def put(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def sync_description():
    """
    Regenerate the marketplace description from what is actually on disk.

    The counts in a marketplace listing are the first thing a person reads and the last
    thing anybody remembers to update. Ours advertised nine agents and eight hooks while
    the repository held ten and sixteen, and then went stale again the moment a
    seventeenth skill landed. check_version_consistency catches it; this stops it
    happening.
    """
    s = len(list((ROOT / "skills").glob("*/SKILL.md")))
    a = len(list((ROOT / "agents").glob("*.agent.md")))
    c = len(list((ROOT / "commands").glob("*.md")))
    h = len(list((ROOT / "hooks").glob("*.hook.md")))
    data = load(".claude-plugin/marketplace.json")
    old = data["plugins"][0].get("description", "")
    data["plugins"][0]["description"] = (
        f"AI SDLC orchestrator — {s} skills, {a} agents, {c} commands, {h} executing "
        f"hooks, cross-repo pipelines, blocking grounding gates, policy-governed autonomy, "
        f"enforced token budgets"
    ).replace("—", "—")
    if data["plugins"][0]["description"] != old:
        save(".claude-plugin/marketplace.json", data)
        print(f"marketplace description resynced: {s} skills, {a} agents, {c} commands, {h} hooks")


def current():
    return dig(load("hub.config.json"), ("hub", "version"))


def cmd_show():
    print("Version across the release surface:\n")
    for rel, path in FILES.items():
        print(f"  {dig(load(rel), path):<10} {rel}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut a release")
    parser.add_argument("--version")
    parser.add_argument("--bump", choices=["major", "minor", "patch"])
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--sync-description", action="store_true",
                        help="regenerate the marketplace description from what is on "
                             "disk, without touching the version")
    parser.add_argument("--skip-validate", action="store_true",
                        help="not recommended; the validate step is what makes this safe")
    args = parser.parse_args()

    if args.sync_description:
        sync_description()
        return 0

    if args.show or (not args.version and not args.bump):
        return cmd_show()

    now = current()
    if args.bump:
        major, minor, patch = (int(x) for x in now.split("."))
        target = {"major": f"{major + 1}.0.0",
                  "minor": f"{major}.{minor + 1}.0",
                  "patch": f"{major}.{minor}.{patch + 1}"}[args.bump]
    else:
        target = args.version

    if not SEMVER.match(target):
        print(f"'{target}' is not semver")
        return 2
    if target == now:
        print(f"already at {target}")
        return 0

    before = {rel: load(rel) for rel in FILES}
    for rel, path in FILES.items():
        data = load(rel)
        put(data, path, target)
        save(rel, data)
    print(f"{now} -> {target} across {len(FILES)} file(s)")
    sync_description()

    if args.skip_validate:
        print("--skip-validate: not verified. You are on your own.")
        return 0

    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate-structure.py")],
                            cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        for rel, data in before.items():
            save(rel, data)
        print("\nvalidate-structure.py FAILED — the version bump was REVERTED.")
        print("A repository sitting at a version it cannot validate is worse than one")
        print("that never bumped. Fix the failure below, then re-run.\n")
        print(result.stdout[-2000:])
        return 1

    print("validate-structure.py passed.\n")
    print("Next:")
    print(f"  git add -A && git commit -m \"release: {target}\"")
    print(f"  git tag v{target} && git push origin main --tags")
    print("  Consumers pick it up with:  /plugin marketplace update algoworks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
