#!/usr/bin/env python3
"""
Report where the old `aiorchestrator.*` VS Code settings went. Migrates nothing.

  python migrations/0005-report-settings-migration.py --repo PATH

WHY THIS MIGRATION REPORTS INSTEAD OF MIGRATING
------------------------------------------------
v3.0 configured the orchestrator through VS Code settings. v3.1 splits that surface three
ways — the plugin's `userConfig`, `hub.config.json`, and the JSON files under `config/` —
because the orchestrator is no longer a VS Code extension and most of these values now
have to be readable by a hook running in a terminal with no editor attached.

The obvious move is to read the old settings and write the new ones. This migration
deliberately does not, and the reason is not caution about the code being wrong.

Silently moving somebody's settings between two systems is worse than telling them,
because they cannot audit a move they did not know happened. Their `qualityGateThreshold`
of 95 becomes a number in a file they have never opened; when a gate later blocks a
pipeline they will look in the place they set it, find a setting that no longer does
anything, and have no path from the symptom back to the cause. A migration that writes
config is a migration whose mistakes are invisible; a migration that prints is one whose
output the user reads before anything changes.

The mappings are also not all one-to-one, which is the second reason. Three of these
settings have no v3.1 equivalent at all, and saying so plainly is more useful than
inventing a destination for them. An honest "no equivalent — here is what replaced the
behaviour" outranks a plausible guess at a key name.

WHAT IT READS
-------------
The workspace file at `<repo>/.vscode/settings.json` and, best effort, the user-level
settings file for VS Code and VS Code Insiders on this platform. Nothing is written to any
of them: the dead `aiorchestrator.*` keys are left exactly where they are, and removing
them is a one-line edit the user makes when they are ready.

VS Code settings files are JSON with comments and trailing commas, which `json.loads`
rejects. The reader here strips both while respecting string literals. It is a tolerant
reader rather than a JSONC parser, so when it still cannot parse a file it says so and
prints the full mapping table anyway — an unreadable settings file is a reason to hand
over the whole table, not a reason to report nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _lib import read_json  # noqa: E402

MIGRATION = "0005-report-settings-migration"
INSTALL_FILE = ".github/orchestrator-install.json"
PREFIX = "aiorchestrator."

# key -> (v3.0 default, where it lives now, what to do about it)
MAPPING = {
    "hubRepository": (
        "algoworks/ai-orchestrator-hub",
        "hub.config.json -> hub.repository",
        "Set once in the hub, not per developer. The plugin is fetched from the "
        "marketplace entry instead: /plugin marketplace add <owner>/<repo>.",
    ),
    "hubBranch": (
        "main",
        "hub.config.json -> hub.branch",
        "Same file, same reasoning.",
    ),
    "autoSync": (
        True,
        "no equivalent",
        "There is no workspace-open sync to enable any more. The plugin carries the "
        "content and is updated deliberately: /plugin marketplace update algoworks, then "
        "python scripts/orchestrator.py upgrade.",
    ),
    "autoContext": (
        True,
        "no direct equivalent",
        "The context-staleness hook reports a context older than "
        "sync/default-sync-config.json -> repoContext.staleThresholdDays; regenerating is "
        "/init or python scripts/context-gen.py --force. Reporting replaced acting.",
    ),
    "qualityGateThreshold": (
        80,
        "plugin userConfig -> quality_gate_threshold",
        "Set at /plugin install time or in the plugin's configuration.",
    ),
    "crossRepoEnabled": (
        True,
        "no equivalent",
        "Cross-repo orchestration is a skill plus registry/connected-repos.yml. It is "
        "enabled by having entries in the registry, not by a flag.",
    ),
    "memoryAutoLearn": (
        True,
        "plugin userConfig -> hooks_enabled / hook_profile",
        "Capture is the learning-capture hook. It writes candidates for triage rather "
        "than writing shared memory directly; python scripts/memory.py review promotes.",
    ),
    "structuralGraphEnabled": (
        True,
        "no equivalent",
        "The structural graph is built on demand by scripts/graph.py and the "
        "structural-graph skill. Nothing runs it in the background, so there is nothing "
        "to switch off.",
    ),
    "groundingEnabled": (
        True,
        "plugin userConfig -> grounding_enabled",
        "Same meaning: verify referenced files and symbols before a skill runs.",
    ),
    "eagerBudgetChars": (
        0,
        "config/token-budgets.json -> eager.totalChars",
        "A real ceiling now rather than an override of one. Changing it is governed by "
        "the ratchet protocol recorded in that file.",
    ),
    "orgProfile": (
        "algoworks",
        "hub.config.json -> overlay.profile (and plugin userConfig -> org_profile)",
        "Must match a folder under overlays/.",
    ),
    "telemetryEnabled": (
        False,
        "plugin userConfig -> hook_profile",
        "The telemetry hook runs at the profiles that include it. It stays local; nothing "
        "leaves the machine.",
    ),
    "excludeFromGit": (
        True,
        "python scripts/gitignore.py apply | remove",
        "An explicit command rather than a setting, because it edits .gitignore and sets "
        "index bits — effects that should follow from something a person typed. "
        "Migrations 0003 and 0004 reconcile what the old setting left behind.",
    ),
}


class MigrationError(RuntimeError):
    """
    Part of the migration contract, kept here for symmetry with the other four. Nothing in
    this file raises it: a migration that only reads and prints has no failure that should
    stop an upgrade, and an unreadable settings file is reported as unreadable rather than
    treated as an error.
    """


def read_state(repo: Path, options: dict | None = None) -> dict:
    return {
        "repo": repo,
        "install": read_json(repo / INSTALL_FILE),
        "options": options or {},
    }


def strip_jsonc(text: str) -> str:
    """
    Remove // and /* */ comments and trailing commas, leaving string literals alone.
    A comment marker inside a string is content, and stripping it would corrupt a value
    such as a URL — which is exactly the sort of setting people put in these files.
    """
    out = []
    index, length, in_string = 0, len(text), False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        out.append(char)
        index += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def candidate_settings_files(repo: Path) -> list:
    """Workspace settings first, then the user-level file for each VS Code flavour."""
    files = [repo / ".vscode" / "settings.json"]
    home = Path.home()
    for flavour in ("Code", "Code - Insiders"):
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                files.append(Path(appdata) / flavour / "User" / "settings.json")
        elif sys.platform == "darwin":
            files.append(home / "Library" / "Application Support" / flavour / "User" / "settings.json")
        else:
            files.append(home / ".config" / flavour / "User" / "settings.json")
    return files


def load_settings(path: Path) -> tuple:
    """Returns (mapping, error). Either the parsed object or a reason it is unavailable."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, str(exc)
    try:
        value = json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as exc:
        return None, f"could not parse even after stripping comments: {exc}"
    return (value, None) if isinstance(value, dict) else (None, "top level is not an object")


def collect(repo: Path) -> dict:
    """Every aiorchestrator.* key found, with the file it came from."""
    found, unreadable = [], []
    for path in candidate_settings_files(repo):
        if not path.is_file():
            continue
        settings, error = load_settings(path)
        if error:
            unreadable.append((str(path), error))
            continue
        for key, value in settings.items():
            if key.startswith(PREFIX):
                found.append({"file": str(path), "key": key,
                              "short": key[len(PREFIX):], "value": value})
    return {"found": found, "unreadable": unreadable}


def applies_to(state: dict) -> bool:
    """Applies when any `aiorchestrator.*` setting is still present anywhere we can see,
    or when a settings file exists that we could not read — an unreadable file may hold
    settings, and reporting the possibility beats asserting there were none."""
    result = collect(state["repo"])
    return bool(result["found"] or result["unreadable"])


def migrate(state: dict) -> dict:
    """
    Reports. Writes nothing — not the settings files, not the install state, not
    hub.config.json. The report IS the migration.
    """
    result = collect(state["repo"])
    customized, defaulted, unknown = [], [], []
    for entry in result["found"]:
        mapping = MAPPING.get(entry["short"])
        if mapping is None:
            unknown.append(entry)
            continue
        default, destination, note = mapping
        record = {**entry, "default": default, "destination": destination, "note": note}
        (customized if entry["value"] != default else defaulted).append(record)
    return {
        "migration": MIGRATION,
        "status": "reported",
        "customized": customized,
        "defaulted": defaulted,
        "unknown": unknown,
        "unreadable": result["unreadable"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report the v3.0 settings migration")
    parser.add_argument("--repo", default=".", help="the consumer repository to inspect")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    state = read_state(repo)

    try:
        if not applies_to(state):
            print(f"{MIGRATION}: skipped — no aiorchestrator.* settings found in this "
                  f"workspace or in the user settings this platform exposes.")
            return 0
        report = migrate(state)
    except MigrationError as exc:
        print(f"{MIGRATION}: FAILED — {exc}", file=sys.stderr)
        return 1

    print(f"{MIGRATION}: REPORT ONLY — nothing was changed, moved, or written.")
    print("  The v3.0 VS Code settings below no longer do anything. Their v3.1 homes:")

    if report["customized"]:
        print(f"\n  {len(report['customized'])} setting(s) you had CUSTOMIZED — these carry "
              f"a decision somebody made, so they are the ones to re-apply:")
        for entry in report["customized"]:
            print(f"    {entry['key']} = {json.dumps(entry['value'])}   "
                  f"(default was {json.dumps(entry['default'])})")
            print(f"      now: {entry['destination']}")
            print(f"      {entry['note']}")
            print(f"      from: {entry['file']}")

    if report["defaulted"]:
        print(f"\n  {len(report['defaulted'])} setting(s) present at the old default — "
              f"nothing to re-apply, but they are dead keys now:")
        for entry in report["defaulted"]:
            print(f"    {entry['key']} = {json.dumps(entry['value'])}  ->  {entry['destination']}")

    if report["unknown"]:
        print(f"\n  {len(report['unknown'])} setting(s) this migration does not recognise. "
              f"They are named rather than ignored, because a key we cannot map is a "
              f"decision we cannot account for:")
        for entry in report["unknown"]:
            print(f"    {entry['key']} = {json.dumps(entry['value'])}   ({entry['file']})")

    if report["unreadable"]:
        print(f"\n  {len(report['unreadable'])} settings file(s) could not be read. They may "
              f"contain settings not listed above:")
        for path, why in report["unreadable"]:
            print(f"    {path}: {why}")
        print("    The full mapping table is in this script's MAPPING block; check by hand.")

    print("\n  The dead keys are left in place. Removing them is your edit to make, and")
    print("  leaving them costs nothing but a line in a file — a migration that tidied")
    print("  somebody's settings.json without being asked would be the behaviour this")
    print("  file exists to avoid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
