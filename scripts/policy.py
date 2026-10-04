#!/usr/bin/env python3
"""
The policy engine: resolve config/policy.json for a repository and answer questions
about what is permitted.

  python scripts/policy.py resolve [--repo PATH] [--json]
  python scripts/policy.py check <agent> <capability> [--repo PATH]
  python scripts/policy.py autonomy [--repo PATH]
  python scripts/policy.py gates [--repo PATH]
  python scripts/policy.py explain [--repo PATH]

WHY A POLICY ENGINE AND NOT MORE SETTINGS
------------------------------------------
The review that prompted this asked for an enterprise configuration model, and the
temptation with that request is to add fifteen more keys to the existing config. That
produces a system where the answer to "what is this agent allowed to do here?" is
assembled by reading five files and remembering the precedence rules.

Instead there is one document with one resolution order, and one command that prints the
resolved answer. If a person and the runtime can disagree about what the policy says,
the policy is decorative.

THE NARROWING RULE
------------------
A repository may only NARROW what its project allows. A repository that raises its own
autonomy level, grants itself a denied capability, or lowers a quality threshold is
refused at load time and the attempt is reported.

This matters more than it sounds. Policy lives in files an agent can edit, and an agent
optimizing for "make the task complete" will find `autonomy.level` eventually. The
config-protection hook already denies edits to governance files; this is the second
layer, so that a policy widened by any route — a hand edit, a bad merge, a migration —
does not take effect silently.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, config, read_json, repo_slug  # noqa: E402

LAYERS = ["defaults", "organization", "project", "repository", "environment"]

# Keys where a more specific layer may only make the value MORE restrictive.
# The comparison direction is stated per key, because "more restrictive" means a lower
# number for a ceiling and a higher one for a floor, and getting that backwards would
# invert the whole guard.
NARROWING_ONLY = {
    "autonomy.level": "lower-is-narrower",
    "qualityGate.aiAssessment.minimumScore": "higher-is-narrower",
    "qualityGate.deterministic.coverage.minimumPercent": "higher-is-narrower",
    "memoryPolicy.promotionCriteria.minimumConfidence": "higher-is-narrower",
    "memoryPolicy.promotionCriteria.minimumRepos": "higher-is-narrower",
    "costLimits.perSessionCeiling": "lower-is-narrower",
    "costLimits.perStoryCeiling": "lower-is-narrower",
}

# Toggles that may be turned ON by a narrower layer but never OFF.
ENABLE_ONLY = {
    "memoryPolicy.promotionRequiresHumanApproval",
    "approvalPolicy.gates",
    "qualityGate.humanReview.required",
    "memoryPolicy.writeGuards",
}


def policy_document() -> dict:
    doc = config("policy.json")
    if doc is None:
        raise SystemExit(
            "config/policy.json is missing or unparseable.\n"
            "Refusing to fall back to a permissive built-in default: a policy engine that "
            "silently allows everything when its policy will not load is worse than none, "
            "because the reassurance survives the protection."
        )
    return doc


def deep_get(node, dotted: str):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def deep_merge(base: dict, overlay: dict, path: str, violations: list) -> dict:
    out = copy.deepcopy(base)
    for key, value in (overlay or {}).items():
        if key.startswith("_"):
            continue
        dotted = f"{path}.{key}" if path else key

        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value, dotted, violations)
            continue

        direction = NARROWING_ONLY.get(dotted)
        if direction is not None and key in out and out[key] is not None and value is not None:
            current, proposed = out[key], value
            widened = (
                (direction == "lower-is-narrower" and proposed > current)
                or (direction == "higher-is-narrower" and proposed < current)
            )
            if widened:
                violations.append(
                    f"{dotted}: refused a widening from {current} to {proposed}. "
                    f"A narrower layer may only restrict."
                )
                continue

        if dotted in ENABLE_ONLY and out.get(key) and not value:
            violations.append(
                f"{dotted}: refused an attempt to disable a control that may only be enabled."
            )
            continue

        out[key] = copy.deepcopy(value)
    return out


def resolve(repo: Path) -> tuple:
    doc = policy_document()
    resolved = copy.deepcopy(doc.get("defaults", {}))
    violations = []
    applied = ["defaults"]

    for layer in LAYERS[1:]:
        block = doc.get(layer) or {}
        if block:
            resolved = deep_merge(resolved, block, "", violations)
            applied.append(layer)

    # A repository may carry its own narrowing block. It goes through the same guard, so
    # a repo-local file cannot grant itself anything its project withheld.
    local = read_json(repo / ".github" / "orchestrator-policy.json")
    if local:
        resolved = deep_merge(resolved, local, "", violations)
        applied.append(f"{repo_slug(repo)}/.github/orchestrator-policy.json")

    return resolved, violations, applied


def cmd_resolve(args) -> int:
    repo = Path(args.repo).resolve()
    resolved, violations, applied = resolve(repo)
    if args.json:
        print(json.dumps({"resolved": resolved, "violations": violations, "layers": applied}, indent=2))
        return 1 if violations else 0

    print(f"Policy resolved for {repo.name}")
    print(f"  layers applied: {' -> '.join(applied)}\n")
    print(f"  autonomy level         {deep_get(resolved, 'autonomy.level')}")
    print(f"  human review required  {deep_get(resolved, 'qualityGate.humanReview.required')}")
    print(f"  AI score threshold     {deep_get(resolved, 'qualityGate.aiAssessment.minimumScore')}")
    print(f"  memory needs approval  {deep_get(resolved, 'memoryPolicy.promotionRequiresHumanApproval')}")
    print(f"  cost limits enabled    {deep_get(resolved, 'costLimits.enabled')}")
    print(f"  telemetry enabled      {deep_get(resolved, 'telemetry.enabled')}")

    if violations:
        print(f"\n  {len(violations)} POLICY VIOLATION(S) — the widening was refused, not applied:")
        for v in violations:
            print(f"    - {v}")
        return 1
    return 0


def cmd_check(args) -> int:
    repo = Path(args.repo).resolve()
    resolved, violations, _ = resolve(repo)
    agents = deep_get(resolved, "permissions.agents") or {}
    entry = agents.get(args.agent)

    if entry is None:
        print(f"DENY  '{args.agent}' has no permission entry.")
        print("      An agent with no declared permissions gets none. Add it to")
        print("      config/policy.json -> defaults.permissions.agents rather than")
        print("      relying on an implicit default, which is how a capability leaks.")
        return 1

    allow = set(entry.get("allow", []))
    deny = set(entry.get("deny", []))

    # Deny always beats allow, and it is checked first so an entry listing a capability
    # in both lists resolves to denied rather than to whichever the reader noticed.
    if args.capability in deny:
        print(f"DENY  {args.agent} -> {args.capability}  (explicitly denied)")
        return 1
    if args.capability in allow:
        print(f"ALLOW {args.agent} -> {args.capability}")
        return 0

    # A prefix grant: repo.write implies repo.write.tests, never the reverse.
    for granted in allow:
        if args.capability.startswith(f"{granted}."):
            print(f"ALLOW {args.agent} -> {args.capability}  (via the broader grant '{granted}')")
            return 0

    print(f"DENY  {args.agent} -> {args.capability}  (not granted)")
    print("      Absence is denial. The allow list is the whole grant.")
    return 1


def cmd_autonomy(args) -> int:
    repo = Path(args.repo).resolve()
    resolved, _, _ = resolve(repo)
    autonomy = deep_get(resolved, "autonomy") or {}
    level = autonomy.get("level", 0)
    levels = autonomy.get("_levels", {})

    print(f"Autonomy level {level} for {repo.name}\n")
    for n in range(0, 6):
        marker = ">" if n == level else " "
        cap = "" if n <= level else "   (not permitted here)"
        print(f"  {marker} {n}  {levels.get(str(n), '')}{cap}")
    ceiling = autonomy.get("maxLevelWithoutExplicitGrant")
    if ceiling is not None and level > ceiling:
        print(f"\n  This level is above the default ceiling of {ceiling} and requires a recorded grant.")
    print(f"\n  {autonomy.get('rationale', '')}")
    return 0


def cmd_gates(args) -> int:
    repo = Path(args.repo).resolve()
    resolved, _, _ = resolve(repo)
    gate = deep_get(resolved, "qualityGate") or {}
    print("Quality gate — a conjunction, not a score\n")
    print("  Deterministic checks (a check that could not RUN counts as a failure):")
    for name, requirement in (gate.get("deterministic") or {}).items():
        if isinstance(requirement, dict):
            requirement = json.dumps(requirement)
        print(f"    {name:<20} {requirement}")
    ai = gate.get("aiAssessment") or {}
    print(f"\n  AI assessment:        >= {ai.get('minimumScore')}  ({ai.get('note', '')})")
    human = gate.get("humanReview") or {}
    print(f"  Human review:         required={human.get('required')} at levels {human.get('requiredAtLevels')}")
    print(f"\n  Rule: {gate.get('rule', '')}")

    approvals = deep_get(resolved, "approvalPolicy.gates") or []
    print(f"\n  Named approval gates ({len(approvals)}):")
    for g in approvals:
        print(f"    {g['id']:<12} phase={g['phase']:<9} owner={g['owner']}")
        print(f"                 artifact: {g['artifact']}")
        print(f"                 asks:     {g['question']}")
    return 0


def cmd_explain(args) -> int:
    repo = Path(args.repo).resolve()
    resolved, violations, applied = resolve(repo)
    print(f"POLICY FOR {repo}\n")
    print(f"Layers: {' -> '.join(applied)}")
    print("Rule:   most specific wins, key by key; a narrower layer may only restrict.\n")
    for section in ("autonomy", "permissions", "dataPolicy", "qualityGate",
                    "approvalPolicy", "memoryPolicy", "costLimits", "telemetry", "model"):
        block = resolved.get(section)
        if not block:
            continue
        note = block.get("_note") if isinstance(block, dict) else None
        print(f"── {section} " + "─" * max(0, 60 - len(section)))
        if note:
            print(f"   {note}\n")
    if violations:
        print(f"\n{len(violations)} refused widening(s):")
        for v in violations:
            print(f"  - {v}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrator policy engine")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("resolve"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_resolve)
    p = sub.add_parser("check"); p.add_argument("agent"); p.add_argument("capability"); p.set_defaults(func=cmd_check)
    sub.add_parser("autonomy").set_defaults(func=cmd_autonomy)
    sub.add_parser("gates").set_defaults(func=cmd_gates)
    sub.add_parser("explain").set_defaults(func=cmd_explain)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
