#!/usr/bin/env python3
"""
Telemetry rollup: turn the local ledgers into the three views a stakeholder asks for.

  python scripts/telemetry.py rollup [--since ISO] [--repo NAME] [--json]
  python scripts/telemetry.py verify           # hash-chain integrity of both ledgers
  python scripts/telemetry.py status
  python scripts/telemetry.py budget           # cost ceilings from policy vs actuals

WHY THIS EXISTS
---------------
`config/policy.json` declared `costLimits.trackedBy: "scripts/telemetry.py rollup"`
before this file did. That is precisely the defect this whole system is built to remove —
a documented mechanism with no executor — and it deserves naming rather than quietly
fixing, because it happened in the file that governs the other gates.

A review of the earlier architecture asked for engineering, AI and financial metrics.
This produces all three from data that was already being written, and reports the parts
it cannot compute as not computed rather than estimating them into existence.

WHAT IT WILL NOT DO
-------------------
It will not invent a dollar figure. `config/model-pricing.json` ships with null prices, so
until somebody fills it in from the official pricing page the financial view reports
TOKENS — which are counted — and says the money column is not configured. A finance
conversation started from a fabricated number is worse than one started from "we have not
measured that yet", and a system whose stated purpose is preventing confident invention
cannot be the thing inventing it.

It will not claim a productivity delta. Nothing here observes what an engineer would have
done without the tool, so "hours saved" is not derivable from these ledgers. What IS
derivable is cycle time, gate pass rates, rework and rejection — and those are real.

READS, NEVER WRITES
-------------------
Local files only, no network, and it never modifies a ledger. The ledgers are
hash-chained; a rollup that rewrote one would break the chain it is meant to verify.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, config, state_home  # noqa: E402


def ledger(*parts) -> Path:
    return state_home().joinpath(*parts)


def read_jsonl(path: Path, since: str | None = None) -> list:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and str(row.get("at", "")) < since:
            continue
        rows.append(row)
    return rows


def verify_chain(path: Path) -> dict:
    """Each line carries prev = sha256 of the previous raw line. Tamper-evident."""
    if not path.exists():
        return {"path": str(path), "exists": False, "lines": 0, "ok": True, "brokenAt": None}
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    prev = "genesis"
    for number, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return {"path": str(path), "exists": True, "lines": len(lines),
                    "ok": False, "brokenAt": number, "reason": "unparseable line"}
        if row.get("prev") != prev:
            return {"path": str(path), "exists": True, "lines": len(lines),
                    "ok": False, "brokenAt": number, "reason": "prev hash mismatch"}
        prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return {"path": str(path), "exists": True, "lines": len(lines), "ok": True, "brokenAt": None}


# ------------------------------------------------------------------ engineering

def pipeline_metrics(repo: str | None) -> dict:
    """
    From the checkpoints, not from a ledger — the pipeline writes its own state and it is
    the only place phase timings and gate outcomes actually exist.
    """
    sessions = ROOT / "memory" / "sessions"
    if not sessions.is_dir():
        return {"pipelines": 0}

    pipelines, gate_waits, phase_failures = [], [], Counter()
    for path in sorted(sessions.glob("*.checkpoint.json")):
        try:
            cp = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if repo and cp.get("repo") != repo:
            continue
        pipelines.append(cp)
        for name, phase in (cp.get("phases") or {}).items():
            if phase.get("status") == "failed":
                phase_failures[name] += 1
            if phase.get("attempts", 0) > 1:
                phase_failures[f"{name} (retried)"] += phase["attempts"] - 1
            if phase.get("gateArtifactAt") and phase.get("verdict"):
                gate_waits.append(name)

    completed = [p for p in pipelines if p.get("status") == "complete"]
    durations = []
    for p in completed:
        try:
            start = datetime.fromisoformat(str(p["startedAt"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(p["updatedAt"]).replace("Z", "+00:00"))
            durations.append((end - start).total_seconds() / 3600)
        except (KeyError, ValueError):
            continue

    scores = [
        phase.get("score")
        for p in pipelines for phase in (p.get("phases") or {}).values()
        if isinstance(phase.get("score"), int)
    ]

    return {
        "pipelines": len(pipelines),
        "completed": len(completed),
        "abandoned": len([p for p in pipelines if p.get("status") == "abandoned"]),
        "inFlight": len([p for p in pipelines if p.get("status") == "active"]),
        "medianCycleTimeHours": round(sorted(durations)[len(durations) // 2], 2) if durations else None,
        "compactionsSurvived": sum(p.get("compactions", 0) for p in pipelines),
        "phaseFailures": dict(phase_failures.most_common(10)),
        "gatesAnswered": len(gate_waits),
        "meanQualityScore": round(sum(scores) / len(scores), 1) if scores else None,
    }


# ------------------------------------------------------------------ AI behaviour

def ai_metrics(turns: list) -> dict:
    tools = Counter()
    for row in turns:
        for name, count in (row.get("toolCounts") or {}).items():
            tools[name] += count
    profiles = Counter(row.get("hookProfile", "unknown") for row in turns)
    return {
        "turns": len(turns),
        "sessions": len({row.get("sessionId") for row in turns if row.get("sessionId")}),
        "toolCalls": sum(tools.values()),
        "topTools": dict(tools.most_common(10)),
        "hookProfiles": dict(profiles),
        "notMeasured": [
            "acceptance rate — needs a signal for whether a human kept the change; "
            "the closest proxy today is gate verdicts",
            "hallucination rate — the eval suite measures it on fixed cases, not in the wild",
            "hours saved — nothing here observes the counterfactual, so it is not derivable",
        ],
    }


def memory_metrics() -> dict:
    entries = []
    index = ROOT / "memory" / "index" / "entries.json"
    if index.exists():
        try:
            entries = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            entries = []
    states = Counter(e.get("state", "candidate") for e in entries)
    return {
        "total": len(entries),
        "byState": dict(states),
        "shared": len([e for e in entries if e.get("scope") == "shared"]),
        "awaitingApproval": states.get("pending-approval", 0),
        "rejected": states.get("rejected", 0),
    }


# ------------------------------------------------------------------ financial

def cost_metrics(calls: list) -> dict:
    ok = [c for c in calls if c.get("ok")]
    tokens_in = sum(c.get("estimatedInputTokens", 0) for c in ok)
    tokens_out = sum(c.get("estimatedOutputTokens", 0) for c in ok)
    priced = [c for c in ok if c.get("cost") is not None]
    by_model = Counter(c.get("model") or "unknown" for c in ok)

    pricing = config("model-pricing.json", {}) or {}
    configured = [m for m, v in (pricing.get("models") or {}).items() if v.get("input") is not None]

    return {
        "headlessCalls": len(calls),
        "successful": len(ok),
        "failed": len(calls) - len(ok),
        "estimatedInputTokens": tokens_in,
        "estimatedOutputTokens": tokens_out,
        "tokenBasis": "chars/4 — an estimate, labelled as one",
        "byModel": dict(by_model),
        "pricingConfigured": bool(configured),
        "cost": round(sum(c["cost"] for c in priced), 4) if priced else None,
        "costNote": None if priced else (
            "not configured — config/model-pricing.json ships with null prices on purpose. "
            "Fill it from the official pricing page and commit the date it was read. Tokens "
            "above are the honest half of the answer."
        ),
    }


# ------------------------------------------------------------------ commands

def cmd_rollup(args) -> int:
    turns = read_jsonl(ledger("telemetry.jsonl"), args.since)
    calls = read_jsonl(ledger("llm", "llm.jsonl"), args.since)
    if args.repo:
        turns = [t for t in turns if t.get("repo") == args.repo]

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "since": args.since,
        "repo": args.repo,
        "engineering": pipeline_metrics(args.repo),
        "ai": ai_metrics(turns),
        "memory": memory_metrics(),
        "financial": cost_metrics(calls),
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    eng, ai, mem, fin = report["engineering"], report["ai"], report["memory"], report["financial"]

    print("Orchestrator telemetry rollup")
    print(f"  generated {report['generatedAt']}"
          + (f" · since {args.since}" if args.since else "")
          + (f" · repo {args.repo}" if args.repo else ""))

    if not turns and not calls and not eng.get("pipelines"):
        print("\n  No data. Telemetry is default-off — switch it on with:")
        print("    ORCHESTRATOR_TELEMETRY=on")
        print("  It is off by default because telemetry somebody did not enable is")
        print("  telemetry they did not consent to.")
        return 0

    print("\n── Engineering " + "─" * 50)
    print(f"  pipelines            {eng['pipelines']}  "
          f"({eng['completed']} complete · {eng['inFlight']} in flight · {eng['abandoned']} abandoned)")
    if eng.get("medianCycleTimeHours") is not None:
        print(f"  median cycle time    {eng['medianCycleTimeHours']}h")
    if eng.get("meanQualityScore") is not None:
        print(f"  mean quality score   {eng['meanQualityScore']}")
    print(f"  gates answered       {eng['gatesAnswered']}")
    print(f"  compactions survived {eng['compactionsSurvived']}"
          + ("   (each one is state the PreCompact hook saved)" if eng["compactionsSurvived"] else ""))
    if eng.get("phaseFailures"):
        print("  rework by phase:")
        for name, count in eng["phaseFailures"].items():
            print(f"    {name:<24} {count}")

    print("\n── AI behaviour " + "─" * 49)
    print(f"  turns                {ai['turns']} across {ai['sessions']} session(s)")
    print(f"  tool calls           {ai['toolCalls']}")
    for name, count in list(ai["topTools"].items())[:6]:
        print(f"    {name:<24} {count}")
    if ai["hookProfiles"]:
        print(f"  hook profiles        {ai['hookProfiles']}")

    print("\n── Memory " + "─" * 55)
    print(f"  entries              {mem['total']}  ({mem['shared']} shared)")
    print(f"  awaiting approval    {mem['awaitingApproval']}"
          + ("   <- run: python scripts/memory.py pending" if mem["awaitingApproval"] else ""))
    print(f"  rejected             {mem['rejected']}")

    print("\n── Financial " + "─" * 52)
    print(f"  headless calls       {fin['headlessCalls']}  "
          f"({fin['successful']} ok · {fin['failed']} failed)")
    print(f"  estimated tokens     {fin['estimatedInputTokens']:,} in · "
          f"{fin['estimatedOutputTokens']:,} out   [{fin['tokenBasis']}]")
    if fin["cost"] is not None:
        print(f"  estimated cost       {fin['cost']}")
    else:
        print(f"  cost                 NOT CONFIGURED")
        print(f"    {fin['costNote']}")

    print("\n── Deliberately not measured " + "─" * 36)
    for item in ai["notMeasured"]:
        print(f"  · {item}")
    print("\n  These are absent rather than estimated. An invented productivity number in a")
    print("  system whose purpose is preventing confident invention would be a poor look.")
    return 0


def cmd_verify(args) -> int:
    results = [verify_chain(ledger("telemetry.jsonl")),
               verify_chain(ledger("security", "egress.jsonl"))]
    bad = 0
    print("Ledger chain integrity\n")
    for r in results:
        if not r["exists"]:
            print(f"  (none)  {r['path']}")
            continue
        if r["ok"]:
            print(f"  OK      {r['lines']} line(s)  {r['path']}")
        else:
            print(f"  BROKEN  at line {r['brokenAt']} ({r.get('reason')})  {r['path']}")
            bad += 1
    if bad:
        print("\n  A broken chain means a line was edited or removed. These ledgers are")
        print("  tamper-EVIDENT, not tamper-proof — this is the evidence, not the prevention.")
    return 1 if bad else 0


def cmd_status(args) -> int:
    enabled = (config("policy.json", {}) or {}).get("defaults", {}).get("telemetry", {})
    print("Telemetry")
    print(f"  policy enabled       {enabled.get('enabled')}")
    print(f"  scope                {enabled.get('scope')} · network {enabled.get('network')}")
    for name, path in (("turns", ledger("telemetry.jsonl")),
                       ("llm calls", ledger("llm", "llm.jsonl")),
                       ("egress", ledger("security", "egress.jsonl"))):
        count = len(read_jsonl(path))
        print(f"  {name:<20} {count:>6} line(s)   {path}")
    print("\n  Nothing here leaves the machine. There is no network import in the")
    print("  telemetry path and there is not going to be one.")
    return 0


def cmd_budget(args) -> int:
    limits = ((config("policy.json", {}) or {}).get("defaults") or {}).get("costLimits") or {}
    calls = read_jsonl(ledger("llm", "llm.jsonl"))
    fin = cost_metrics(calls)

    print("Cost ceilings (config/policy.json -> costLimits)\n")
    print(f"  enabled              {limits.get('enabled')}")
    if not limits.get("enabled"):
        print("    Off by default: a limit nobody set is a limit nobody agreed to.")
    for key in ("perSessionCeiling", "perStoryCeiling", "perRepoMonthlyCeiling"):
        print(f"  {key:<20} {limits.get(key)}")
    print(f"  onExceed             {limits.get('onExceed')}")

    print(f"\n  actual (estimated)   {fin['estimatedInputTokens']:,} in · "
          f"{fin['estimatedOutputTokens']:,} out tokens")
    if fin["cost"] is None:
        print("  actual cost          not computable — prices are unset")
        print("\n  A ceiling cannot be enforced against a cost that is not being computed.")
        print("  Fill config/model-pricing.json before enabling costLimits, or the limit is")
        print("  a number in a file rather than a control.")
        return 0
    print(f"  actual cost          {fin['cost']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Telemetry rollup")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("rollup")
    p.add_argument("--since"); p.add_argument("--repo"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_rollup)

    sub.add_parser("verify").set_defaults(func=cmd_verify)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("budget").set_defaults(func=cmd_budget)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
