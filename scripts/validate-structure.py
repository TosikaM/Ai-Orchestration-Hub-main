#!/usr/bin/env python3
"""
Orchestrator Hub structure validator.

  python scripts/validate-structure.py

Checks the manifest, frontmatter, syntax, the token ratchet, least-privilege tool
declarations, hook wiring, eval wiring, generated-content freshness, plane separation,
and organization neutrality. Exit 0 = clean, exit 1 = at least one error.

A NOTE ON WHAT THIS FILE IS FOR
-------------------------------
Most of these checks exist because a specific class of failure already happened
somewhere, and each one is cheap to keep and expensive to have skipped:

  - A hook documented in Markdown that nothing executes. Five of those shipped once,
    counted in a capability inventory as though they were a working surface.
  - A ceiling that became a string after a bad merge, so the comparison silently
    stopped comparing rather than failing.
  - A context layer with a cap but no entry in the priority order, so it was never
    sent to the model — logged to a channel nobody had open.
  - A command mapped to a skill that does not exist.
  - A generated file hand-edited, forking it from its source with no way to notice.

Several checks guard other checks. That is deliberate: a gate an agent or a careless
merge can disable is not a gate, and every quality claim this system makes is defined
in a file somebody can edit.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402
from _lib import (  # noqa: E402
    AGENTS, BUILTIN_COMMANDS, COMMANDS, CONTEXTS, HOOKS, KNOWN_TOOLS,
    MUTATING_TOOLS, READ_ONLY_SKILLS, ROOT, SKILLS,
    frontmatter, measure_discovery, read_json,
)

try:
    import yaml
except ImportError:
    sys.stderr.write("pip install pyyaml\n")
    sys.exit(2)


REQUIRED_FILES = [
    "README.md", "ARCHITECTURE-AND-SETUP.md", "CONTRIBUTING.md", "SECURITY.md",
    "THIRD-PARTY-NOTICES.md", "CLAUDE.md",
    "hub.config.json", "orchestrator-hub.yml", "package.json",
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "hooks/hooks.json",
    "config/stack-mappings.json", "config/pipeline-graph.json",
    "config/architecture-baseline.json", "config/architecture-baseline.schema.json",
    "config/token-budgets.json", "config/tool-registry.json",
    "config/redaction-patterns.json", "config/install-profiles.json",
    "hooks/runtime/run.js", "hooks/runtime/dispatch.js",
    "hooks/runtime/flags.js", "hooks/runtime/registry.json",
    "lib/config.js", "lib/paths.js", "lib/state.js", "lib/redact.js",
    "memory/README.md",
    "memory/shared/anti-patterns.md", "memory/shared/best-practices.md",
    "memory/shared/instincts.md", "memory/shared/tool-chains.md",
    "memory/shared/skill-evolution-log.md",
    "memory/repos/TEMPLATE-context.md",
    "registry/connected-repos.yml", "registry/active-session.json",
    "sync/default-sync-config.json", "sync/sync-config.schema.json",
    "evals/evals.json", "evals/evals.schema.json", "evals/touchfiles.json",
    "evals/eval-runner.py",
    "instructions/orchestrator-connector.instructions.md",
    "instructions/skill-invoker.instructions.md",
    "knowledge/README.md",
    "content-src/preamble/grounding-contract.md",
    "scripts/gen-content.py", "scripts/measure-discovery-budget.py",
    "scripts/context-bill.py", "scripts/orchestrator.py",
]

# --- Organization neutrality (golden rule G4) -------------------------------------
# hub.config.json and overlays/ are the sanctioned homes for an org-identifying string.
FORBIDDEN_ORG_PATTERN = re.compile(r"charlesschwab|schwab", re.IGNORECASE)
ORG_SCAN_SUFFIXES = {".ts", ".js", ".json", ".yml", ".yaml", ".md", ".py", ".ps1", ".tmpl"}
ORG_SCAN_EXCLUDE_DIRS = {
    "node_modules", "out", "dist", ".git", "overlays", "__pycache__", ".venv",
    "runs", "inbox", "extracted",
}
# Files that legitimately contain the pattern because they ARE the detector, or because
# they document what was removed. Without these the gate fails on itself.
ORG_SCAN_EXCLUDE_FILES = {
    "validate-structure.py",
    "audit.ps1",
    "ci.yml",
    "AI-ORCHESTRATOR-MASTER-BLUEPRINT.md",
    "hub.config.json",
}
ORG_SCAN_EXCLUDE_FILES_PIN = 5


# ============================================================== manifest checks

def check_required_files(root: Path):
    return [f"missing required file: {name}" for name in REQUIRED_FILES
            if not (root / name).exists()]


def check_agents(root: Path):
    errors = []
    for agent in AGENTS:
        path = root / "agents" / f"{agent}.agent.md"
        if not path.exists():
            errors.append(f"missing agent: {path.name} (generate with scripts/gen-content.py)")
            continue
        meta, problem = frontmatter(path)
        if problem:
            errors.append(f"{path.name}: {problem}")
            continue
        for field in ("name", "description"):
            if field not in meta:
                errors.append(f"{path.name}: frontmatter is missing '{field}'")
        if meta.get("name") != agent:
            errors.append(f"{path.name}: frontmatter name is '{meta.get('name')}', expected '{agent}'")
        body = path.read_text(encoding="utf-8")
        if "## Prompt Defense Baseline" not in body:
            errors.append(
                f"{path.name}: no Prompt Defense Baseline. Every agent needs a stated identity "
                f"boundary — the hub distributes Markdown into contexts automatically."
            )
    return errors


def check_skills(root: Path):
    errors = []
    for skill in SKILLS:
        path = root / "skills" / skill / "SKILL.md"
        if not path.exists():
            errors.append(f"missing skill: skills/{skill}/SKILL.md")
            continue
        meta, problem = frontmatter(path)
        if problem:
            errors.append(f"{skill}: {problem}")
            continue
        for field in ("name", "description"):
            if field not in meta:
                errors.append(f"{skill}: frontmatter is missing '{field}'")
        if meta.get("name") != skill:
            errors.append(f"{skill}: frontmatter name is '{meta.get('name')}', expected the folder name")
        description = str(meta.get("description", ""))
        if "\n" in description:
            errors.append(f"{skill}: description contains a line break — it must be one sentence")
        body = path.read_text(encoding="utf-8")
        if "## Routing" not in body:
            errors.append(f"{skill}: SKILL.md has no '## Routing' block")
        if "## Lessons Learned" not in body:
            errors.append(f"{skill}: SKILL.md has no '## Lessons Learned' section")
        if "NOT FOR:" in body and "that is `" not in body:
            errors.append(
                f"{skill}: the NOT FOR clause does not name a destination skill. "
                f"'NOT FOR: writing code' is useless; 'NOT FOR: writing code — that is "
                f"`cqrs-developer`' routes correctly."
            )
    return errors


def check_commands(root: Path):
    errors = []
    for command in COMMANDS:
        for directory, suffix in (("commands", ".md"), ("prompts", ".prompt.md")):
            path = root / directory / f"{command}{suffix}"
            if not path.exists():
                errors.append(f"missing {directory}/{command}{suffix}")
    return errors


def check_contexts(root: Path):
    return [f"missing context: contexts/{name}.md"
            for name in CONTEXTS if not (root / "contexts" / f"{name}.md").exists()]


# ============================================================== the token ratchet

def check_discovery_budget(root: Path):
    errors = []
    budget_path = root / "config" / "token-budgets.json"
    if not budget_path.exists():
        return ["config/token-budgets.json missing — cannot check the discovery budget"]
    budgets = read_json(budget_path)
    if budgets is None:
        return ["config/token-budgets.json is not valid JSON"]

    per_skill_cap = budgets["discovery"]["perSkillFrontmatterBytes"]
    aggregate_cap = budgets["discovery"]["aggregateFrontmatterBytes"]
    total, per_skill = measure_discovery(root)

    for name, size in per_skill:
        if size > per_skill_cap:
            errors.append(
                f"{name}: frontmatter name+description is {size}B, over the {per_skill_cap}B "
                f"per-skill limit. Move triggers / USE FOR / NOT FOR into the '## Routing' body."
            )
    if total > aggregate_cap:
        errors.append(
            f"aggregate skill frontmatter is {total}B, over the {aggregate_cap}B ceiling. "
            f"This text loads in every session in every repo."
        )
    else:
        pct = round(total / aggregate_cap * 100, 1)
        _lib.info(f"discovery footprint: {total}B / {aggregate_cap}B ({pct}%)")
    return errors


def check_budget_provenance(root: Path):
    """
    The ratchet's mutation pins. A ceiling whose recorded measurement is missing, stale,
    or non-numeric is a DISABLED ceiling wearing the costume of an enabled one.
    """
    errors = []
    budgets = read_json(root / "config" / "token-budgets.json")
    if budgets is None:
        return ["config/token-budgets.json missing or unparseable"]

    discovery = budgets.get("discovery", {})
    derivation = discovery.get("derivation")
    if not isinstance(derivation, dict):
        return ["config/token-budgets.json: discovery.derivation block missing"]

    # Pin 1: every ceiling must be a real number. A string ceiling makes the comparison
    # raise or silently stop comparing, rather than failing honestly.
    for key in ("perSkillFrontmatterBytes", "aggregateFrontmatterBytes"):
        value = discovery.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"discovery.{key} is {type(value).__name__}, not int — the ceiling is disabled")
    for layer, value in budgets.get("eager", {}).get("layers", {}).items():
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"eager.layers.{layer} is {type(value).__name__}, not int — the ceiling is disabled")

    # Pin 2: the recorded measurement must exist and match reality.
    recorded = derivation.get("measuredValue")
    if not isinstance(recorded, int):
        errors.append(
            "discovery.derivation.measuredValue is unset. Run "
            "`python scripts/measure-discovery-budget.py` and commit the result."
        )
    else:
        actual, _ = measure_discovery(root)
        if actual != recorded:
            errors.append(
                f"discovery footprint drifted: recorded {recorded}B, actual {actual}B. "
                f"{derivation.get('ratchetProtocol', 'Re-measure and commit in the same commit.')}"
            )

    # Pin 3: every capped layer must be in priority order, and vice versa. A layer with
    # a cap but no priority entry is never sent to the model at all.
    layers = set(budgets.get("eager", {}).get("layers", {}))
    priority = set(budgets.get("priority", []))
    for orphan in sorted(layers - priority):
        errors.append(f"eager.layers.{orphan} has a cap but is absent from `priority` — it will never be sent")
    for ghost in sorted(priority - layers):
        errors.append(f"priority lists '{ghost}' but eager.layers has no cap for it")
    return errors


def check_every_skill_is_budgeted(root: Path):
    """A skill folder nobody listed has never been consciously budgeted."""
    errors = []
    budgets = read_json(root / "config" / "token-budgets.json", {})
    cap = budgets.get("discovery", {}).get("perSkillFrontmatterBytes", "?")
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return ["skills/ directory missing"]
    for skill_dir in sorted(skills_dir.iterdir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        if skill_dir.name not in SKILLS:
            errors.append(
                f"skills/{skill_dir.name}/ exists but is not in scripts/_lib.py SKILLS. "
                f"Add it there and re-run measure-discovery-budget.py, or delete it. "
                f"An unlisted skill is an unbudgeted skill (cap {cap}B)."
            )
    return errors


# ============================================================== least privilege

def check_allowed_tools(root: Path):
    errors = []
    for skill in SKILLS:
        path = root / "skills" / skill / "SKILL.md"
        if not path.exists():
            continue
        meta, problem = frontmatter(path)
        if problem or not meta:
            continue
        tools = meta.get("allowed-tools")
        if not isinstance(tools, list) or not tools:
            errors.append(
                f"{skill}: frontmatter has no 'allowed-tools' list. Least privilege is not "
                f"optional — declare the surface this skill needs."
            )
            continue
        for tool in tools:
            if tool not in KNOWN_TOOLS:
                errors.append(f"{skill}: unknown tool '{tool}' in allowed-tools")
        if skill in READ_ONLY_SKILLS:
            leaked = MUTATING_TOOLS.intersection(tools)
            if leaked:
                errors.append(
                    f"{skill} is a read-only verifier but declares {sorted(leaked)}. "
                    f"Remove them, or remove {skill} from READ_ONLY_SKILLS with a written reason."
                )
    return errors


# ============================================================== wiring parity

def check_command_skill_parity(root: Path):
    """
    Every command must resolve to a skill that exists on disk, and every skill command
    file must have a matching top-level command. A command mapped to nothing is a slash
    command that silently does the default thing.
    """
    errors = []
    owned = {}
    for skill in SKILLS:
        commands_dir = root / "skills" / skill / "commands"
        if not commands_dir.is_dir():
            continue
        for cmd_file in commands_dir.glob("*.md"):
            owned.setdefault(cmd_file.stem, []).append(skill)

    for name, skills in sorted(owned.items()):
        if len(skills) > 1:
            errors.append(f"command '{name}' is claimed by more than one skill: {skills}")
        if name not in COMMANDS:
            errors.append(
                f"skills/{skills[0]}/commands/{name}.md exists but '{name}' is not in COMMANDS "
                f"— no top-level command file will be generated for it"
            )
    for command in COMMANDS:
        if command in BUILTIN_COMMANDS:
            continue
        if command not in owned:
            errors.append(
                f"command '{command}' has no owning skill command file "
                f"(expected skills/<skill>/commands/{command}.md)"
            )
    return errors


def check_hook_runtime_parity(root: Path):
    """
    Every documented hook must have a handler, every handler must be documented, and
    every handler must be reachable from the plugin manifest — directly or through a
    dispatcher. Five hooks once shipped that nothing executed; this is the check that
    would have caught it.
    """
    errors = []
    hooks_dir = root / "hooks"
    handlers_dir = hooks_dir / "runtime" / "handlers"
    registry_path = hooks_dir / "runtime" / "registry.json"
    manifest_path = root / "hooks" / "hooks.json"

    if not registry_path.exists():
        return ["hooks/runtime/registry.json missing — nothing knows which handler serves which hook"]

    documented = {p.name[: -len(".hook.md")] for p in hooks_dir.glob("*.hook.md")}
    implemented = {p.stem for p in handlers_dir.glob("*.js")} if handlers_dir.is_dir() else set()
    registry = read_json(registry_path, {})
    registered = {meta.get("handler") for meta in registry.get("hooks", {}).values()}

    for orphan in sorted(documented - implemented):
        errors.append(f"hooks/{orphan}.hook.md documents a hook with no handler in hooks/runtime/handlers/")
    for ghost in sorted(implemented - documented):
        errors.append(f"hooks/runtime/handlers/{ghost}.js has no hooks/{ghost}.hook.md documenting it")
    for unwired in sorted(implemented - registered):
        errors.append(f"handler '{unwired}' is not in hooks/runtime/registry.json — it will never fire")
    for missing in sorted(registered - implemented):
        if missing:
            errors.append(f"registry.json names handler '{missing}' which does not exist")

    for expected in HOOKS:
        if expected not in documented:
            errors.append(f"hooks/{expected}.hook.md is in the HOOKS inventory but missing on disk")

    # Every hook the registry declares must be reachable from the manifest: named
    # directly in a run.js command, or listed inside a dispatcher that is.
    manifest_text = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""
    dispatched = set()
    for dispatcher_id, dispatcher in registry.get("dispatchers", {}).items():
        if dispatcher_id in manifest_text:
            dispatched.update(dispatcher.get("hookIds", []))
    for hook_id, meta in registry.get("hooks", {}).items():
        if meta.get("event") == "InProcess":
            continue
        if meta.get("note", "").startswith("Registered in the manifest only when"):
            continue
        if meta.get("note", "").startswith("Invoked in-process"):
            continue
        if hook_id not in manifest_text and hook_id not in dispatched:
            errors.append(
                f"hook '{hook_id}' is in registry.json but is not reachable from "
                f"hooks/hooks.json — it will never fire"
            )
    return errors


def check_plugin_manifest_component_keys(root: Path):
    """
    Two keys that must NOT appear in plugin.json, both learned the expensive way.

    `agents` — the Claude Code plugin validator rejects the key outright with
    `agents: Invalid input`, whatever form it takes (string, array of paths, array of
    directories). Agent files under agents/ are auto-discovered by convention. The error
    does not name the cause, so a manifest carrying this key fails to install and the
    message sends you looking at the agent files.

    `hooks` — the standard hooks manifest is auto-loaded by convention, and declaring it
    here produces `Duplicate hooks file detected`. This one has been added and removed
    twice in a project we studied, in response to alternating bug reports, which is why
    it is pinned by a check rather than remembered.

    Both are cheap to assert and expensive to rediscover.
    """
    errors = []
    manifest = read_json(root / ".claude-plugin" / "plugin.json")
    if manifest is None:
        return [".claude-plugin/plugin.json missing or unparseable"]

    if "agents" in manifest:
        errors.append(
            "plugin.json declares 'agents'. The Claude Code plugin validator rejects that "
            "key with `agents: Invalid input` and the error does not name the cause. "
            "Remove it — agents/ is auto-discovered."
        )
    for key in ("skills", "commands"):
        value = manifest.get(key)
        if value is not None and not isinstance(value, list):
            errors.append(
                f"plugin.json '{key}' is {type(value).__name__}, not a list. The validator "
                f"requires arrays even for a single entry."
            )
    return errors


def check_prompt_lifecycle(root: Path):
    """
    Prompt lifecycle metadata: version, owner, lastReviewed, evalIds.

    The failure this prevents is slow and hard to attribute: somebody edits a command's
    wording, quality moves a few points, and nothing connects the two events. Six weeks
    later the question "what changed?" has no answer because the artifact that changed
    carried no version and no owner.

    `evalIds` is the load-bearing field. It names which eval cases exercise this command,
    so a change to the text has a defined blast radius in the suite. An empty list is
    permitted and reported — an honest "nothing tests this" is useful, and a fabricated
    mapping would be worse than none.
    """
    errors = []
    suite = read_json(root / "evals" / "evals.json", {}) or {}
    known = {c["id"] for c in suite.get("testCases", [])}
    untested = []

    for command in COMMANDS:
        path = root / "commands" / f"{command}.md"
        if not path.exists():
            continue
        meta, problem = frontmatter(path)
        if problem or not meta:
            continue
        for field in ("version", "owner", "lastReviewed", "evalIds"):
            if field not in meta:
                errors.append(f"commands/{command}.md: frontmatter is missing '{field}'")
        version = str(meta.get("version", ""))
        if version and not re.match(r"^\d+\.\d+\.\d+$", version):
            errors.append(f"commands/{command}.md: version '{version}' is not semver")
        ids = meta.get("evalIds")
        if ids is None:
            continue
        if not isinstance(ids, list):
            errors.append(f"commands/{command}.md: evalIds must be a list")
            continue
        for eid in ids:
            if eid not in known:
                errors.append(
                    f"commands/{command}.md: evalIds names '{eid}', which is not in "
                    f"evals/evals.json — a selector pointing at nothing selects nothing"
                )
        if not ids:
            untested.append(command)

    if untested:
        _lib.info(f"commands with no eval coverage ({len(untested)}): {', '.join(untested)}")
    return errors


def check_version_consistency(root: Path):
    """
    One version, three files. They drift the moment a release is cut by hand.

    hub.config.json is the source of truth for the hub version; plugin.json and
    marketplace.json must agree with it, because the marketplace resolves an install by
    the version IN THE CATALOG while the plugin reports the version in its own manifest.
    A mismatch installs one thing and reports another, and `orchestrator.py upgrade`
    compares the two to decide whether migrations are due — so drift here quietly breaks
    the upgrade path rather than the install.

    Also checks that the marketplace description's advertised counts match what is
    actually shipped. That string is the first thing a person reads and the last thing
    anybody remembers to update; ours advertised nine agents and eight hooks while the
    repository held ten and sixteen.
    """
    errors = []
    hub = read_json(root / "hub.config.json", {}) or {}
    plugin = read_json(root / ".claude-plugin" / "plugin.json", {}) or {}
    market = read_json(root / ".claude-plugin" / "marketplace.json", {}) or {}

    canonical = (hub.get("hub") or {}).get("version")
    if not canonical:
        return ["hub.config.json has no hub.version — nothing to compare against"]

    if plugin.get("version") != canonical:
        errors.append(
            f"plugin.json version {plugin.get('version')!r} != hub.config.json {canonical!r}"
        )
    entries = market.get("plugins") or []
    for entry in entries:
        if entry.get("version") != canonical:
            errors.append(
                f"marketplace.json plugin {entry.get('name')!r} version "
                f"{entry.get('version')!r} != hub.config.json {canonical!r}"
            )
        if entry.get("name") != (hub.get("plugin") or {}).get("name"):
            errors.append(
                f"marketplace.json plugin name {entry.get('name')!r} != "
                f"hub.config.json plugin.name {(hub.get('plugin') or {}).get('name')!r}"
            )

    actual = {
        "skills": len(list((root / "skills").glob("*/SKILL.md"))),
        "agents": len(list((root / "agents").glob("*.agent.md"))),
        "commands": len(list((root / "commands").glob("*.md"))),
        "hooks": len(list((root / "hooks").glob("*.hook.md"))),
    }
    for entry in entries:
        description = str(entry.get("description", ""))
        for noun, count in actual.items():
            match = re.search(rf"(\d+)\s+{noun}\b", description)
            if match and int(match.group(1)) != count:
                errors.append(
                    f"marketplace.json advertises {match.group(1)} {noun} but the "
                    f"repository ships {count}"
                )
    return errors


def check_no_hooks_in_plugin_manifest(root: Path):
    """
    Claude Code auto-loads hooks/hooks.json by convention. Declaring `hooks`
    in plugin.json as well produces a duplicate-detection error, and it is a mistake
    that gets re-learned repeatedly because the failure message does not name the cause.
    """
    manifest = read_json(root / ".claude-plugin" / "plugin.json")
    if manifest is None:
        return [".claude-plugin/plugin.json missing or unparseable"]
    if "hooks" in manifest:
        return [
            "plugin.json declares 'hooks'. Claude Code auto-loads hooks/hooks.json; "
            "declaring it here causes a duplicate-hooks error. Remove the key."
        ]
    return []


def check_eval_wiring(root: Path):
    """
    Two rots this catches: a case with no touchfile entry never runs on a diff, so it
    is decoration; and a touchfile entry for a deleted case is a selector that silently
    selects nothing.
    """
    errors = []
    suite = read_json(root / "evals" / "evals.json")
    if suite is None:
        return ["evals/evals.json missing or unparseable"]
    touch_path = root / "evals" / "touchfiles.json"
    if not touch_path.exists():
        return ["evals/touchfiles.json missing — every eval would run on every diff"]
    touch = read_json(touch_path, {})

    case_ids = {c["id"] for c in suite.get("testCases", [])}
    mapped = set(touch.get("cases", {}))
    for orphan in sorted(case_ids - mapped):
        errors.append(f"{orphan} has no entry in evals/touchfiles.json — it will never be diff-selected")
    for ghost in sorted(mapped - case_ids):
        errors.append(f"evals/touchfiles.json references {ghost}, which is not in evals.json")
    for case in suite.get("testCases", []):
        if case.get("tier") not in ("gate", "periodic"):
            errors.append(f"{case['id']}: tier must be 'gate' or 'periodic'")
        if case.get("agent") not in AGENTS:
            errors.append(f"{case['id']}: agent '{case.get('agent')}' is not a declared agent")
    return errors


# ============================================================== guard the guards

def check_org_exclusions_unchanged(root: Path):
    """
    ORG_SCAN_EXCLUDE_FILES is the neutrality gate's own escape hatch. Growing it is how
    a neutrality gate quietly stops being one. Pin the count; a legitimate addition
    updates the pin in the same commit, which makes it a reviewable line in the diff.
    """
    actual = len(ORG_SCAN_EXCLUDE_FILES)
    if actual != ORG_SCAN_EXCLUDE_FILES_PIN:
        return [
            f"ORG_SCAN_EXCLUDE_FILES has {actual} entries, pinned at {ORG_SCAN_EXCLUDE_FILES_PIN}. "
            f"Every entry is a file allowed to contain a forbidden org string. If the addition "
            f"is correct, update ORG_SCAN_EXCLUDE_FILES_PIN in the same commit and say why."
        ]
    return []


def check_plane_separation(root: Path):
    """
    The view plane reads files and writes exactly one thing: a gate verdict. If it ever
    needs orchestration logic, that is the signal the boundary was drawn wrong — not a
    reason to widen this check.
    """
    errors = []
    view_src = root / "view" / "src"
    if not view_src.is_dir():
        return []
    forbidden_write = re.compile(
        r"writeFile|writeFileSync|appendFile|mkdirSync|rmSync|unlinkSync", re.IGNORECASE
    )
    allowed_marker = "gate-verdict-write"
    for path in view_src.rglob("*.ts"):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if forbidden_write.search(line) and allowed_marker not in text:
                errors.append(
                    f"view/src/{path.relative_to(view_src).as_posix()}:{number}: the view plane "
                    f"writes to disk. It may write only the gate verdict; mark that call site "
                    f"with a '{allowed_marker}' comment if this is it."
                )
                break
    return errors


# ============================================================== syntax + freshness

def check_yaml(root: Path):
    errors = []
    for path in root.rglob("*.yml"):
        if any(part in ORG_SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid YAML: {exc}")
    return errors


def check_json(root: Path):
    errors = []
    for path in root.rglob("*.json"):
        if any(part in ORG_SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in ("package-lock.json",):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON: {exc}")
    return errors


def check_sync_config(root: Path):
    path = root / "sync" / "default-sync-config.json"
    if not path.exists():
        return ["sync/default-sync-config.json missing"]
    config = read_json(path)
    if config is None:
        return ["sync/default-sync-config.json is not valid JSON"]
    errors = []
    for key in ("hubRepository", "hubBranch", "subscriptions"):
        if key not in config:
            errors.append(f"sync config is missing '{key}'")
    for subscription in config.get("subscriptions", []):
        missing = [k for k in ("type", "remotePath", "localPath") if k not in subscription]
        if missing:
            errors.append(f"subscription missing {missing}: {subscription}")
    return errors


def check_generated_freshness(root: Path):
    """A hand-edited generated file is a fork of its source that nobody will notice."""
    generator = root / "scripts" / "gen-content.py"
    if not generator.exists():
        return ["scripts/gen-content.py missing — cannot verify generated content"]
    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        capture_output=True, text=True, cwd=str(root),
    )
    if result.returncode == 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_org_neutrality(root: Path):
    """Golden rule G4: no foreign organization string outside hub.config.json and overlays/."""
    errors = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in ORG_SCAN_SUFFIXES:
            continue
        if any(part in ORG_SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in ORG_SCAN_EXCLUDE_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_ORG_PATTERN.search(line):
                errors.append(f"{path.relative_to(root)}:{number}: foreign org reference")
    return errors


# ============================================================== driver

CHECKS = [
    ("Required files", check_required_files),
    ("Agents", check_agents),
    ("Skills", check_skills),
    ("Commands and prompts", check_commands),
    ("Contexts", check_contexts),
    ("Discovery token budget", check_discovery_budget),
    ("Budget provenance (ratchet pins)", check_budget_provenance),
    ("Every skill is budgeted", check_every_skill_is_budgeted),
    ("Least privilege (allowed-tools)", check_allowed_tools),
    ("Command/skill parity", check_command_skill_parity),
    ("Hook runtime parity", check_hook_runtime_parity),
    ("No hooks key in plugin.json", check_no_hooks_in_plugin_manifest),
    ("Plugin manifest component keys", check_plugin_manifest_component_keys),
    ("Version consistency", check_version_consistency),
    ("Eval wiring", check_eval_wiring),
    ("Prompt lifecycle", check_prompt_lifecycle),
    ("Org exclusion pin", check_org_exclusions_unchanged),
    ("Plane separation", check_plane_separation),
    ("YAML syntax", check_yaml),
    ("JSON syntax", check_json),
    ("Sync config", check_sync_config),
    ("Generated content freshness", check_generated_freshness),
    ("Org neutrality", check_org_neutrality),
]


def main() -> int:
    root = ROOT
    print("Validating Orchestrator Hub structure...")
    print(f"Root: {root}\n")

    all_errors = []
    for name, check in CHECKS:
        try:
            errors = check(root)
        except Exception as exc:  # a broken check is a failure, never a pass
            errors = [f"the check itself raised {type(exc).__name__}: {exc}"]
        if errors:
            _lib.fail(f"{name}: {len(errors)} error(s)")
            for error in errors[:20]:
                print(f"       - {error}")
            if len(errors) > 20:
                print(f"       ... and {len(errors) - 20} more")
            all_errors.extend(errors)
        else:
            _lib.ok(name)

    print()
    if all_errors:
        print(f"FAILED: {len(all_errors)} total error(s)")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
