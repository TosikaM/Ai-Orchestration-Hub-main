#!/usr/bin/env python3
"""
Context bill of materials.

  python scripts/context-bill.py              # the full bill
  python scripts/context-bill.py --budget     # grade against the ceilings, exit 1 on a violation
  python scripts/context-bill.py --diff       # only what this branch changed
  python scripts/context-bill.py --json       # machine-readable

WHY THIS EXISTS
---------------
A design principle that says the token economy is "enforced, not aspirational" invites
one fair question: show me the bill. Before this script there was no answer. There was a
single line in a chat response reporting the eager total during an invocation, and no way
at all to ask "what does this repository cost me before I type anything?" or "did that
skill edit make things worse?"

The `context-budget` skill was specified to audit token consumption and then remediate.
It had no instrument. It was an auditor with no ledger.

TWO LEDGERS, AND CONFUSING THEM IS HOW A BUDGET BECOMES THEATER
---------------------------------------------------------------
  ALWAYS-ON       skill frontmatter (name + description). Parsed and held in context in
                  every session, in every repo, for every user, before anyone types.
  PER-INVOCATION  SKILL.md body plus its command file. Paid once, when that command runs.

A kilobyte in the first column costs orders of magnitude more than a kilobyte in the
second. Optimizing the wrong one is arithmetic, not engineering.

`references/` material is progressive-disclosure: counted here, never charged, because
it loads only when a skill asks for it.

HONEST LABELING
---------------
Every number here is a chars-divided-by-four ESTIMATE and says so on every rendering.
Do not put an estimate in front of a stakeholder as a measurement. A predecessor of this
system claimed a specific token-savings percentage in two places with no measurement
anywhere in the repository; that figure was deleted rather than propagated, and this
script exists so the honest version can be produced instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, budgets as load_budgets, frontmatter_and_body  # noqa: E402


def utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def build_bill() -> dict:
    budgets = load_budgets()
    per_token = budgets.get("charsPerTokenEstimate", 4)
    skills = []

    skills_dir = ROOT / "skills"
    for skill_dir in sorted(skills_dir.iterdir()) if skills_dir.is_dir() else []:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, body = frontmatter_and_body(skill_md)
        always_on = utf8_len(f"{meta.get('name', '')}{meta.get('description', '')}")
        eager_body = utf8_len(body)

        commands_dir = skill_dir / "commands"
        command_files = sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []
        # Only ONE command file loads per invocation, so the eager cost is the worst
        # single command, not their sum. Summing them is the most common way a bill
        # like this overstates by 3x and gets ignored.
        worst_command = max((utf8_len(f.read_text(encoding="utf-8")) for f in command_files), default=0)

        references_dir = skill_dir / "references"
        reference_bytes = sum(
            utf8_len(f.read_text(encoding="utf-8"))
            for f in sorted(references_dir.glob("*.md"))
        ) if references_dir.is_dir() else 0

        eager = eager_body + worst_command
        skills.append({
            "skill": skill_dir.name,
            "alwaysOnBytes": always_on,
            "alwaysOnTokens": ceil_div(always_on, per_token),
            "eagerBytes": eager,
            "eagerTokens": ceil_div(eager, per_token),
            "commandCount": len(command_files),
            "onDemandBytes": reference_bytes,
        })

    agents_dir = ROOT / "agents"
    agents = []
    for agent_file in sorted(agents_dir.glob("*.agent.md")) if agents_dir.is_dir() else []:
        meta, body = frontmatter_and_body(agent_file)
        agents.append({
            "agent": agent_file.name[: -len(".agent.md")],
            # An agent description is read when deciding whether to delegate, so it is
            # always-on in the same sense skill frontmatter is.
            "alwaysOnBytes": utf8_len(f"{meta.get('name', '')}{meta.get('description', '')}"),
            "bodyBytes": utf8_len(body),
        })

    # Commands are always-on too. Every command's `description` is held so the model can
    # route to it, exactly like a skill's. Omitting them under-reported the real cost by
    # roughly two thirds — `claude plugin details` charges ~2,280 always-on tokens where
    # the skills-only figure implied ~470.
    commands_dir = ROOT / "commands"
    commands = []
    for command_file in sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []:
        meta, _ = frontmatter_and_body(command_file)
        commands.append({
            "command": command_file.stem,
            "alwaysOnBytes": utf8_len(str(meta.get("description", ""))),
        })

    memory_bytes = 0
    memory_dir = ROOT / "memory" / "shared"
    if memory_dir.is_dir():
        memory_bytes = sum(utf8_len(f.read_text(encoding="utf-8")) for f in memory_dir.glob("*.md"))

    return {
        "estimate": True,
        "charsPerTokenEstimate": per_token,
        "skills": skills,
        "agents": agents,
        "commands": commands,
        "totals": {
            "skillCount": len(skills),
            "agentCount": len(agents),
            "alwaysOnSkillBytes": sum(s["alwaysOnBytes"] for s in skills),
            "alwaysOnAgentBytes": sum(a["alwaysOnBytes"] for a in agents),
            "alwaysOnCommandBytes": sum(c["alwaysOnBytes"] for c in commands),
            "alwaysOnTotalBytes": (
                sum(s["alwaysOnBytes"] for s in skills)
                + sum(a["alwaysOnBytes"] for a in agents)
                + sum(c["alwaysOnBytes"] for c in commands)
            ),
            "alwaysOnTokens": ceil_div(
                sum(s["alwaysOnBytes"] for s in skills)
                + sum(a["alwaysOnBytes"] for a in agents)
                + sum(c["alwaysOnBytes"] for c in commands),
                per_token,
            ),
            "worstEagerBytes": max((s["eagerBytes"] for s in skills), default=0),
            "worstEagerTokens": max((s["eagerTokens"] for s in skills), default=0),
            "onDemandBytes": sum(s["onDemandBytes"] for s in skills),
            "sharedMemoryBytes": memory_bytes,
        },
    }


def grade(bill: dict) -> list:
    budgets = load_budgets()
    violations = []
    discovery = budgets.get("discovery", {})
    per_skill_cap = discovery.get("perSkillFrontmatterBytes", 240)
    aggregate_cap = discovery.get("aggregateFrontmatterBytes", 4000)
    layers = budgets.get("eager", {}).get("layers", {})
    eager_cap = layers.get("skillMd", 8000) + layers.get("commandFile", 2000)

    for s in bill["skills"]:
        if s["alwaysOnBytes"] > per_skill_cap:
            violations.append(
                f"{s['skill']}: {s['alwaysOnBytes']}B always-on > {per_skill_cap}B cap "
                f"(move triggers into '## Routing')"
            )
        if s["eagerBytes"] > eager_cap:
            violations.append(
                f"{s['skill']}: {s['eagerBytes']}B eager > {eager_cap}B "
                f"(move reference material into references/)"
            )
    total_always_on = bill["totals"]["alwaysOnSkillBytes"]
    if total_always_on > aggregate_cap:
        violations.append(
            f"aggregate skill always-on {total_always_on}B > {aggregate_cap}B ceiling"
        )
    return violations


def changed_files() -> set:
    for ref in ("origin/main", "main", "HEAD~1"):
        result = subprocess.run(
            ["git", "diff", "--name-only", ref], capture_output=True, text=True, cwd=str(ROOT),
        )
        if result.returncode == 0:
            return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return set()


def render(bill: dict, only: set | None = None) -> None:
    print(f"Context bill of materials   (ESTIMATE at {bill['charsPerTokenEstimate']} chars/token)\n")
    rows = sorted(bill["skills"], key=lambda x: -x["alwaysOnBytes"])
    if only is not None:
        rows = [r for r in rows if any(f"skills/{r['skill']}/" in c for c in only)]
        if not rows:
            print("No skill changed on this branch.")
            return

    print(f"{'skill':<28}{'always-on':>12}{'eager':>10}{'on-demand':>12}")
    print("-" * 62)
    for s in rows:
        print(f"{s['skill']:<28}{s['alwaysOnBytes']:>10}B{s['eagerTokens']:>9}t{s['onDemandBytes']:>11}B")

    t = bill["totals"]
    print("-" * 62)
    print(f"{'TOTAL (' + str(t['skillCount']) + ' skills)':<28}"
          f"{t['alwaysOnSkillBytes']:>10}B{t['worstEagerTokens']:>9}t{t['onDemandBytes']:>11}B")
    print(f"{'+ ' + str(t['agentCount']) + ' agent descriptions':<28}{t['alwaysOnAgentBytes']:>10}B")
    print(f"{'+ ' + str(len(bill['commands'])) + ' command descriptions':<28}{t['alwaysOnCommandBytes']:>10}B")
    print(f"{'= ALWAYS-ON TOTAL':<28}{t['alwaysOnTotalBytes']:>10}B  ~{t['alwaysOnTokens']}t")
    print(f"{'shared memory':<28}{t['sharedMemoryBytes']:>10}B")
    print()
    print("Always-on is paid every session, in every repo, before the user types.")
    print("It is SKILLS + AGENTS + COMMANDS — all three carry a description the model")
    print("holds in order to route. Cross-check against the platform's own figure with:")
    print("  claude plugin details orchestrator@algoworks")
    print("Theirs is authoritative; a large gap means this ledger is measuring the wrong thing.")
    print("Eager shown is the WORST single invocation, not a sum — one skill loads per command.")
    print("On-demand (references/) is not charged unless a skill asks for it.")
    print()
    print("These are estimates. Do not present them as measurements.")


def main() -> int:
    bill = build_bill()

    if "--json" in sys.argv:
        print(json.dumps(bill, indent=2))
        return 0

    only = changed_files() if "--diff" in sys.argv else None
    render(bill, only)

    if "--budget" in sys.argv:
        violations = grade(bill)
        if violations:
            print(f"\nBUDGET VIOLATIONS ({len(violations)}):")
            for v in violations:
                print(f"  - {v}")
            return 1
        print("\nWithin budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
