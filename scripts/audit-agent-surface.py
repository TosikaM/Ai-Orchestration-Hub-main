#!/usr/bin/env python3
"""
Audit our own agent surface — the eighth security pass.

  python scripts/audit-agent-surface.py [--repo PATH]

THE REFRAME
-----------
Agent configuration is an attack surface, and it is one this system generates and
distributes. The other seven security passes look at the consumer's code. This one looks
at what the orchestrator wrote into the consumer's repository — which is the
highest-privilege text there, because it goes straight into a model's instructions with
no human reading it first.

Given that the hub is an automatic, on-open distribution channel, and that learning
capture writes agent output into shared memory which syncs organization-wide, auditing
the consumer's code and not our own output is the wrong way round.

SCOPE
-----
Six checks against a known surface. Deliberately not a general-purpose agent security
scanner — a narrow scope we can keep honest beats a broad one we cannot.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    INJECTION_MARKERS, ROOT, config, frontmatter, read_json,
)

FINDINGS = []


def finding(severity: str, location: str, issue: str, fix: str) -> None:
    FINDINGS.append({"severity": severity, "location": location, "issue": issue, "fix": fix})


def check_prompt_defense(root: Path) -> None:
    """1. Every agent carries a stated identity boundary."""
    agents_dir = root / "agents"
    for path in sorted(agents_dir.glob("*.agent.md")) if agents_dir.is_dir() else []:
        text = path.read_text(encoding="utf-8")
        if "## Prompt Defense Baseline" not in text:
            finding(
                "HIGH", f"agents/{path.name}",
                "no Prompt Defense Baseline — this agent has no stated identity boundary",
                "add {{PROMPT_DEFENSE}} to content-src/agents/"
                f"{path.name}.tmpl and re-run gen-content.py",
            )


def check_allowed_tools(root: Path) -> None:
    """2. Every skill declares its tool surface."""
    skills_dir = root / "skills"
    for skill_dir in sorted(skills_dir.iterdir()) if skills_dir.is_dir() else []:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, problem = frontmatter(skill_md)
        if problem or not meta:
            continue
        if not meta.get("allowed-tools"):
            finding(
                "MEDIUM", f"skills/{skill_dir.name}/SKILL.md",
                "no allowed-tools declaration — this skill runs with whatever the session has",
                "declare the minimum surface this skill actually needs",
            )


def check_hook_interpolation(root: Path) -> None:
    """3. No hook command string interpolates a repo-derived value."""
    manifest_path = root / "hooks" / "hooks.json"
    manifest = read_json(manifest_path)
    if manifest is None:
        finding("HIGH", "hooks/hooks.json", "missing or unparseable",
                "restore the manifest; without it no hook fires")
        return
    # ${CLAUDE_PLUGIN_ROOT} is supplied by the platform and is the sanctioned exception.
    suspicious = re.compile(r"\$\{(?!CLAUDE_PLUGIN_ROOT)[^}]+\}|\$\([^)]+\)|`[^`]+`")
    for event, groups in manifest.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if suspicious.search(command):
                    finding(
                        "HIGH", f"hooks/hooks.json ({event})",
                        f"hook command interpolates a value: {command[:110]}",
                        "hook commands must be literal except for ${CLAUDE_PLUGIN_ROOT}; "
                        "resolve anything else inside run.js where it can be validated",
                    )


def check_mcp_declarations(root: Path, repo: Path) -> None:
    """4. No connector is enabled that the registry does not sanction."""
    registry = config("tool-registry.json", {}) or {}
    sanctioned = set(registry.get("defaults", {}).get("enabledConnectors", []))
    sanctioned |= set(registry.get("optional", {}).keys())

    for candidate in (repo / ".mcp.json", root / ".mcp.json"):
        data = read_json(candidate)
        if not data:
            continue
        for name in (data.get("mcpServers") or {}):
            if name not in sanctioned:
                finding(
                    "MEDIUM", candidate.name,
                    f"connector '{name}' is enabled but absent from tool-registry.json",
                    "add it to config/tool-registry.json with a fallback and a health probe, "
                    "or remove it — every MCP tool description is always-on context",
                )

    plugin = read_json(root / ".claude-plugin" / "plugin.json", {}) or {}
    shipped = plugin.get("mcpServers") or {}
    if shipped:
        finding(
            "MEDIUM", ".claude-plugin/plugin.json",
            f"the plugin ships {len(shipped)} MCP connector(s) enabled by default",
            "ship zero. An org declares what it MAY enable in tool-registry.json; a "
            "developer turns one on deliberately.",
        )

    # Governance completeness. A connector is a path by which an agent reaches past the
    # repository into systems other people depend on; an unreviewed one is not a small
    # gap. The required-field list lives in the registry itself so the rule and the
    # enforcement cannot drift apart.
    governance = registry.get("governance") or {}
    required = governance.get("requiredFields") or []
    risk_classes = set((governance.get("riskClasses") or {}).keys())

    for name, entry in (registry.get("optional") or {}).items():
        missing = [f for f in required if f not in entry]
        if missing:
            finding(
                "MEDIUM", f"config/tool-registry.json -> optional.{name}",
                f"ungoverned connector: missing {', '.join(missing)}",
                "every connector needs an owner, an environment, a risk class, an explicit "
                "operation list, an audit flag and an authentication mode — "
                "'the orchestrator has GitHub access' is not a reviewable statement",
            )
            continue

        if entry.get("riskClass") not in risk_classes:
            finding(
                "MEDIUM", f"config/tool-registry.json -> optional.{name}",
                f"riskClass '{entry.get('riskClass')}' is not one of {sorted(risk_classes)}",
                "use a declared risk class; the approval matrix is keyed on it",
            )

        # An unowned connector that can change something colleagues see is a control
        # nobody is accountable for.
        if entry.get("owner") in (None, "", "unassigned") and entry.get("riskClass") in (
            "shared-write", "environment-write", "irreversible",
        ):
            finding(
                "LOW", f"config/tool-registry.json -> optional.{name}",
                f"owner is unassigned on a {entry.get('riskClass')} connector",
                "put a name there before enabling it in an organization with more than one "
                "team. Reported as LOW because nothing is enabled by default — it becomes "
                "the blocking question the moment somebody enables it.",
            )

        if entry.get("riskClass") in ("shared-write", "environment-write") and not entry.get("auditLog"):
            finding(
                "MEDIUM", f"config/tool-registry.json -> optional.{name}",
                f"auditLog is off on a {entry.get('riskClass')} connector",
                "set auditLog true; the registry's own rule requires a receipt before any "
                "shared-write call",
            )

        if entry.get("riskClass") == "irreversible":
            finding(
                "HIGH", f"config/tool-registry.json -> optional.{name}",
                "an irreversible-class connector is declared as optional-and-enableable",
                "irreversible operations are refused from an agent context by the approval "
                "matrix. Remove it, or reclassify it honestly.",
            )


def check_injection_signatures(root: Path, repo: Path) -> None:
    """5. No distributed or synced file matches an injection signature."""
    watched = []
    for base, patterns in (
        (root, ["agents/*.md", "skills/**/*.md", "prompts/*.md", "commands/*.md",
                "contexts/*.md", "instructions/*.md", "memory/shared/*.md"]),
        (repo, [".github/agents/*.md", ".github/skills/**/*.md", ".github/prompts/*.md",
                ".github/memory/**/*.md", ".claude/skills/**/*.md"]),
    ):
        for pattern in patterns:
            watched.extend(base.glob(pattern))

    for path in watched:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        match = INJECTION_MARKERS.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            finding(
                "HIGH", f"{path}:{line}",
                f"matches an injection signature: {match.group(0).strip()[:60]}",
                "this file is loaded directly into a model's instructions. Quarantine it "
                "and find out how it got here.",
            )


def check_install_state(repo: Path) -> None:
    """6. Every recorded operation verifies."""
    import hashlib
    state = read_json(repo / ".github" / "orchestrator-install.json")
    if not state:
        return  # not connected; that is not a finding
    for operation in state.get("operations", []):
        if operation.get("op") != "write":
            continue
        path = repo / operation["path"]
        if not path.exists():
            finding("MEDIUM", operation["path"], "recorded as written but missing",
                    "python scripts/orchestrator.py repair")
        elif operation.get("sha256"):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != operation["sha256"]:
                finding("LOW", operation["path"],
                        "modified since install — expected if you edited it deliberately",
                        "a sync backs it up before replacing it; no action needed if intentional")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the orchestrator's own agent surface")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    check_prompt_defense(ROOT)
    check_allowed_tools(ROOT)
    check_hook_interpolation(ROOT)
    check_mcp_declarations(ROOT, repo)
    check_injection_signatures(ROOT, repo)
    check_install_state(repo)

    if args.json:
        print(json.dumps({"findings": FINDINGS}, indent=2))
        return 1 if any(f["severity"] == "HIGH" for f in FINDINGS) else 0

    print("Agent-surface audit (security pass 8)\n")
    if not FINDINGS:
        print("  Clean. No findings.")
        print("\n  Reported as clean deliberately. A scanner that always finds something")
        print("  teaches its readers to ignore it.")
        return 0

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    for f in sorted(FINDINGS, key=lambda x: order.get(x["severity"], 3)):
        print(f"  [{f['severity']:<6}] {f['location']}")
        print(f"           {f['issue']}")
        print(f"           fix: {f['fix']}\n")
    high = sum(1 for f in FINDINGS if f["severity"] == "HIGH")
    print(f"{len(FINDINGS)} finding(s), {high} HIGH.")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
