#!/usr/bin/env python3
"""
The memory system: capture, deduplicate, score, promote, query, prune.

  python scripts/memory.py capture --type anti-pattern --title "..." --resolution "..."
  python scripts/memory.py search "<query>"
  python scripts/memory.py digest                     # the ranked eager-context digest
  python scripts/memory.py promote [--dry-run]
  python scripts/memory.py prune [--yes]
  python scripts/memory.py review                     # triage learning candidates

THIS IS THE ONLY SUPPORTED WRITE PATH, AND THAT IS THE DESIGN
--------------------------------------------------------------
Every write here runs the redaction and injection guard first, and there is no flag that
skips it. Two reasons, and the second is the one people miss.

Shared memory syncs to every connected repository, so a captured credential is not a
local mistake — it is an organization-wide replication event. An agent that debugs an
auth failure and writes "regenerated the token to sk-ant-..." has copied a live secret
into every repo in the company.

And stored memory is re-injected into future prompts, which makes the memory store an
INJECTION surface as well as a storage surface. A resolution note reading "ignore
previous instructions" becomes a delayed instruction: read back to an agent three months
later, in a different repository, with no human in the loop.

The write guard is not a hook, deliberately. Modeling it as an event would leave the
write path unguarded whenever the event failed to fire. Some guards are just a function
you must call, and the honest fix is to make the call site the only way in.

THE CONFIDENCE ARITHMETIC
-------------------------
A promotion rule with no input is a rule that never fires. Confidence is computed:

  initial 0.4        one observation, one repo — deliberately below the 0.7 promotion
                     floor, so no single event can promote anything however sure the
                     capturing agent felt at the time
  +0.15              reinforced in a NEW repo        <- the primary path to promotion
  +0.05              reinforced in a repo already seen
  -0.25              a counter-example was recorded
  -0.05 per 90 days  decay since lastReinforced, applied lazily at READ time
  clamped to [0.1, 0.95]

Decay is for RANKING, never for deletion. Deletion-by-decay stays deferred because
calibrating a rate needs real usage data and a wrong rate silently discards useful
learnings. A ranking decay discards nothing — it only stops a three-year-old instinct
outranking last week's — so a wrong rate there is cheap and correctable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    ROOT, budgets, config, guard_free_text, read_json, repo_slug, utc_now, write_json,
)

SHARED = ROOT / "memory" / "shared"
REPOS = ROOT / "memory" / "repos"
INDEX = ROOT / "memory" / "index"
SESSIONS = ROOT / "memory" / "sessions"

CATEGORY_FILES = {
    "anti-pattern": "anti-patterns.md",
    "best-practice": "best-practices.md",
    "tool-chain": "tool-chains.md",
    "instinct": "instincts.md",
}

INITIAL_CONFIDENCE = 0.4
DELTA_NEW_REPO = 0.15
DELTA_SAME_REPO = 0.05
DELTA_COUNTER_EXAMPLE = -0.25
DELTA_PER_90_DAYS = -0.05
FLOOR, CEILING = 0.1, 0.95
STRONG_MATCH, WEAK_MATCH = 0.72, 0.45
PROMOTION_CONFIDENCE = 0.7
PROMOTION_REPOS = 2


def clamp(value: float) -> float:
    return round(min(CEILING, max(FLOOR, value)), 2)


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\b(the|a|an|is|are|was|were|to|of|in|on|for|and|or|that|this|it)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    """Token-set overlap. Cheap, explainable, and good enough to catch a restatement."""
    left = set(normalize(a).split())
    right = set(normalize(b).split())
    if not left or not right:
        return 0.0
    shared = len(left & right)
    return (2 * shared) / (len(left) + len(right))


# ------------------------------------------------------------------ storage

def entries_path() -> Path:
    return INDEX / "entries.json"


def load_entries() -> list:
    return read_json(entries_path(), []) or []


def save_entries(entries: list) -> None:
    write_json(entries_path(), entries)
    render_markdown(entries)


def render_markdown(entries: list) -> None:
    """
    The JSON index is the store; the Markdown files are a rendering of it.

    One source, two representations. The Markdown is what a human browses and what syncs
    to consumer repositories; the JSON is what ranking and promotion operate on. Writing
    to both by hand would guarantee they disagree within a month.
    """
    SHARED.mkdir(parents=True, exist_ok=True)
    headers = {
        "anti-pattern": ("anti-patterns.md", "# Shared Memory — Anti-Patterns"),
        "best-practice": ("best-practices.md", "# Shared Memory — Best Practices"),
        "tool-chain": ("tool-chains.md", "# Shared Memory — MCP Tool Chains"),
        "instinct": ("instincts.md", "# Global Instincts (Promotion Candidates)"),
    }
    for category, (filename, header) in headers.items():
        # Retired entries are kept in the index — what the organization believed, and
        # when it stopped, is part of the record — but they stop being rendered, which
        # is what stops them being loaded into anybody's context.
        rows = [
            e for e in entries
            if e.get("type") == category
            and e.get("scope") == "shared"
            and e.get("state") != "retired"
        ]
        rows.sort(key=lambda e: -effective_confidence(e))
        lines = [
            header,
            "",
            "<!-- GENERATED from memory/index/entries.json by scripts/memory.py.",
            "     Edit through `python scripts/memory.py`, not by hand: the write path runs",
            "     the redaction and injection guard, and hand edits are lost on the next render. -->",
            "",
        ]
        if not rows:
            lines += ["_No entries yet. Memory ships empty — seeding it with invented learnings",
                      "would poison the well on day one._", ""]
        for e in rows:
            lines += [
                f"### {e['title']}",
                f"- **Confidence**: {effective_confidence(e):.2f} "
                f"(recorded {e.get('confidence', INITIAL_CONFIDENCE):.2f})",
                f"- **Seen in**: {', '.join(e.get('seenInRepos', [])) or 'unknown'}",
                f"- **Context**: {e.get('context', '') or '—'}",
                f"- **Resolution**: {e.get('resolution', '') or '—'}",
                f"- **Applies to**: {e.get('appliesTo', 'all')}",
                f"- **First observed**: {e.get('firstObserved', '?')} · "
                f"**Last reinforced**: {e.get('lastReinforced', '?')}",
            ]
            if e.get("counterExamples"):
                lines.append(f"- **Counter-examples**: {len(e['counterExamples'])}")
            if e.get("crossRef"):
                lines.append(f"- **Related**: {e['crossRef']}")
            lines.append("")
        (SHARED / filename).write_text("\n".join(lines), encoding="utf-8")


def effective_confidence(entry: dict, now: datetime | None = None) -> float:
    """Decay applied lazily at read time. Never mutates the stored value."""
    base = entry.get("confidence", INITIAL_CONFIDENCE)
    stamp = entry.get("lastReinforced") or entry.get("firstObserved")
    if not stamp:
        return clamp(base)
    try:
        last = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return clamp(base)
    now = now or datetime.now(timezone.utc)
    periods = int((now - last).days // 90)
    if periods <= 0:
        return clamp(base)
    return clamp(base + periods * DELTA_PER_90_DAYS)


# ------------------------------------------------------------------ commands

def cmd_capture(args) -> int:
    if args.type not in CATEGORY_FILES:
        print(f"unknown --type '{args.type}'. One of: {', '.join(CATEGORY_FILES)}")
        return 2

    # The guard runs before anything is compared or written. Injection markers and
    # HIGH-tier secrets are never writable; --allow-medium only relaxes the MEDIUM rule
    # that applies when nobody is present to confirm.
    allow_medium = bool(getattr(args, "allow_medium", False))
    try:
        guard_free_text("title", args.title, interactive=allow_medium or None)
        guard_free_text("context", args.context or "", interactive=allow_medium or None)
        guard_free_text("resolution", args.resolution or "", interactive=allow_medium or None)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        print("The learning was not captured. Rewrite it without the flagged content.")
        return 3

    repo = args.repo or repo_slug(Path.cwd())
    entries = load_entries()
    same_type = [e for e in entries if e.get("type") == args.type]

    best, best_score = None, 0.0
    for existing in same_type:
        # Compare on TITLE and RESOLUTION, never on CONTEXT. Context is repo-specific
        # and differs even when the lesson is word-for-word identical, so including it
        # guarantees you never detect a duplicate.
        score = max(
            similarity(args.title, existing.get("title", "")),
            similarity(args.resolution or "", existing.get("resolution", "")),
        )
        if score > best_score:
            best, best_score = existing, score

    if best is not None and best_score >= STRONG_MATCH:
        seen = set(best.get("seenInRepos", []))
        is_new_repo = repo not in seen
        seen.add(repo)
        best["seenInRepos"] = sorted(seen)
        best["confidence"] = clamp(
            best.get("confidence", INITIAL_CONFIDENCE)
            + (DELTA_NEW_REPO if is_new_repo else DELTA_SAME_REPO)
        )
        best["lastReinforced"] = utc_now()
        best["reinforcements"] = best.get("reinforcements", 0) + 1
        save_entries(entries)
        print(f"REINFORCED (match {best_score:.2f}): {best['title']}")
        print(f"  confidence {best['confidence']:.2f} · repos {len(best['seenInRepos'])} "
              f"{'(new repo: +0.15)' if is_new_repo else '(same repo: +0.05)'}")
        if best["confidence"] >= PROMOTION_CONFIDENCE and len(best["seenInRepos"]) >= PROMOTION_REPOS:
            print("  This entry now meets the promotion rule. Run `memory.py promote`.")
        return 0

    entry = {
        "id": f"m-{abs(hash(args.title)) % 0xFFFFFF:06x}",
        "type": args.type,
        "scope": "repo",
        # candidate -> pending-approval -> approved | rejected, and approved -> retired.
        # Everything starts as a candidate. Nothing reaches shared memory without a
        # human naming it as organizational guidance.
        "state": "candidate",
        "title": args.title,
        "context": args.context or "",
        "resolution": args.resolution or "",
        "appliesTo": args.applies_to or "all",
        "seenInRepos": [repo],
        "confidence": INITIAL_CONFIDENCE,
        "firstObserved": utc_now(),
        "lastReinforced": utc_now(),
        "reinforcements": 0,
        "counterExamples": [],
    }
    if best is not None and best_score >= WEAK_MATCH:
        entry["crossRef"] = best["title"]
        print(f"Weak match ({best_score:.2f}) with '{best['title']}' — appended with a cross-reference.")

    entries.append(entry)
    save_entries(entries)
    print(f"CAPTURED: {entry['title']}")
    print(f"  id {entry['id']} · confidence {INITIAL_CONFIDENCE} · scope repo · repo {repo}")
    print(f"  Promotion needs confidence >= {PROMOTION_CONFIDENCE} AND >= {PROMOTION_REPOS} repos.")
    return 0


def cmd_search(args) -> int:
    entries = load_entries()
    if not entries:
        print("Memory is empty.")
        return 0
    repo = repo_slug(Path.cwd())
    scored = []
    for entry in entries:
        text = f"{entry.get('title','')} {entry.get('context','')} {entry.get('resolution','')}"
        relevance = similarity(args.query, text)
        if relevance <= 0.05:
            continue
        confidence = effective_confidence(entry)
        repo_match = 1.15 if repo in entry.get("seenInRepos", []) else 1.0
        scored.append((relevance * confidence * repo_match, relevance, confidence, entry))

    if not scored:
        print(f"No match for '{args.query}'. That is a real answer — do not fill the gap from memory.")
        return 0

    scored.sort(key=lambda row: -row[0])
    print(f"{len(scored)} match(es), ranked by relevance x confidence x repo-match:\n")
    for rank, relevance, confidence, entry in scored[:args.limit]:
        print(f"  [{rank:.3f}] {entry['title']}")
        print(f"          type {entry['type']} · confidence {confidence:.2f} "
              f"· repos {', '.join(entry.get('seenInRepos', []))}")
        if entry.get("resolution"):
            print(f"          {entry['resolution'][:150]}")
        print()
    return 0


def cmd_digest(args) -> int:
    """
    The ranked digest that goes into eager context.

    Ranked by confidence x recency x repo-match and hard-capped, rather than truncated
    by recency alone. Recency is a proxy for relevance that gets steadily worse as the
    store grows — which is to say, exactly as the store becomes valuable.
    """
    limits = budgets().get("memoryRead", {})
    cap = limits.get("maxInjectedInstincts", 6)
    floor = limits.get("minConfidenceForInjection", 0.7)
    repo = repo_slug(Path.cwd())

    entries = [e for e in load_entries() if effective_confidence(e) >= floor]
    entries.sort(
        key=lambda e: -(effective_confidence(e) * (1.15 if repo in e.get("seenInRepos", []) else 1.0))
    )
    selected = entries[:cap]

    if not selected:
        print(f"_No memory entries at or above confidence {floor}._")
        return 0
    print(f"## Memory digest ({len(selected)} of {len(entries)} above confidence {floor})\n")
    for entry in selected:
        print(f"- **{entry['title']}** ({effective_confidence(entry):.2f}) — {entry.get('resolution','')[:180]}")
    if len(entries) > cap:
        print(f"\n_{len(entries) - cap} further entries above the floor were not injected "
              f"(cap {cap}). Query with `/memory search`._")
    return 0


def requires_human_approval() -> bool:
    """
    Read from policy rather than hardcoded, so an organization can decide — but the
    shipped default is True and scripts/policy.py refuses to let a narrower layer turn
    it off (memoryPolicy.promotionRequiresHumanApproval is enable-only).
    """
    policy = config("policy.json", {}) or {}
    memory_policy = (policy.get("defaults") or {}).get("memoryPolicy") or {}
    return memory_policy.get("promotionRequiresHumanApproval", True)


def approval_request_path(entry_id: str) -> Path:
    return SESSIONS / f"memory-approval-{entry_id}.md"


def write_approval_request(entry: dict, confidence: float, repos: int) -> Path:
    """
    The artifact a human reviews. A gate with nothing attached trains people to click
    yes, so the request carries the claim, the evidence, and — most importantly — the
    blast radius of approving it.
    """
    path = approval_request_path(entry["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([
        f"# Memory promotion request — {entry['id']}",
        "",
        f"**{entry['title']}**",
        "",
        f"- **Type:** {entry.get('type')}",
        f"- **Confidence:** {confidence:.2f} (recorded {entry.get('confidence', 0):.2f})",
        f"- **Seen in {repos} repo(s):** {', '.join(entry.get('seenInRepos', []))}",
        f"- **First observed:** {entry.get('firstObserved')}",
        f"- **Last reinforced:** {entry.get('lastReinforced')}",
        f"- **Reinforcements:** {entry.get('reinforcements', 0)}",
        "",
        "## Context",
        "",
        entry.get("context", "") or "_none recorded_",
        "",
        "## Resolution — this is what would become organizational guidance",
        "",
        entry.get("resolution", "") or "_none recorded_",
        "",
        "## What approving this does",
        "",
        "This entry moves into `memory/shared/`, which syncs to every connected repository",
        "and is re-injected as context into future sessions in all of them. Nothing",
        "downstream re-derives it or checks it against the repository it lands in.",
        "",
        "The promotion criteria measure how OFTEN something was observed. They do not",
        "measure whether it is TRUE. That judgement is the reason this gate exists.",
        "",
        "Ask: would you write this on the team wiki as guidance for every project?",
        "",
        "## Decide",
        "",
        "```",
        f"python scripts/memory.py approve {entry['id']} --by \"<your name>\"",
        f"python scripts/memory.py reject  {entry['id']} --reason \"...\"",
        "```",
        "",
    ]), encoding="utf-8")
    return path


def cmd_promote(args) -> int:
    entries = load_entries()
    eligible = []
    for entry in entries:
        if entry.get("scope") == "shared":
            continue
        if entry.get("state") in ("pending-approval", "rejected", "retired"):
            continue
        confidence = effective_confidence(entry)
        repos = len(entry.get("seenInRepos", []))
        if confidence >= PROMOTION_CONFIDENCE and repos >= PROMOTION_REPOS:
            eligible.append((entry, confidence, repos))

    if not eligible:
        print(f"Nothing meets the rule (confidence >= {PROMOTION_CONFIDENCE} AND >= {PROMOTION_REPOS} repos).")
        near = [
            (e, effective_confidence(e), len(e.get("seenInRepos", [])))
            for e in entries
            if e.get("scope") != "shared" and e.get("state") not in ("rejected", "retired")
        ]
        near.sort(key=lambda row: -row[1])
        if near:
            print("\nClosest candidates:")
            for entry, confidence, repos in near[:5]:
                missing = []
                if confidence < PROMOTION_CONFIDENCE:
                    missing.append(f"confidence {confidence:.2f} < {PROMOTION_CONFIDENCE}")
                if repos < PROMOTION_REPOS:
                    missing.append(f"seen in {repos} repo(s), needs {PROMOTION_REPOS}")
                print(f"  - {entry['title']}  ({'; '.join(missing)})")
        pending = [e for e in entries if e.get("state") == "pending-approval"]
        if pending:
            print(f"\n{len(pending)} entr(ies) awaiting a human decision:")
            for entry in pending:
                print(f"  - {entry['id']}  {entry['title']}")
        return 0

    gated = requires_human_approval()
    print(f"{len(eligible)} entr(ies) meet the promotion criteria:\n")
    for entry, confidence, repos in eligible:
        print(f"  {entry['id']}  {entry['title']}")
        print(f"    confidence {confidence:.2f} · seen in {repos} repos: {', '.join(entry['seenInRepos'])}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    if not gated:
        # An organization has explicitly opted out. Do it, and say plainly what was done.
        for entry, _, _ in eligible:
            entry["scope"] = "shared"
            entry["state"] = "approved"
            entry["promotedAt"] = utc_now()
            entry["approvedBy"] = "auto (policy: promotionRequiresHumanApproval=false)"
        save_entries(entries)
        print("\nPromoted automatically — this organization has disabled the approval gate.")
        print("These now load in every repository. A wrong one is wrong everywhere.")
        return 0

    for entry, confidence, repos in eligible:
        entry["state"] = "pending-approval"
        entry["pendingSince"] = utc_now()
        path = write_approval_request(entry, confidence, repos)
        print(f"\n  request written: {path.relative_to(ROOT)}")
    save_entries(entries)

    print("\nMeeting the criteria makes an entry a CANDIDATE, not shared knowledge.")
    print("Confidence and repo-count measure how often something was observed; they do")
    print("not measure whether it is true. A human names it as organizational guidance:")
    print(f"\n  python scripts/memory.py approve <id> --by \"<name>\"")
    print(f"  python scripts/memory.py reject  <id> --reason \"...\"")
    return 0


def _find(entries: list, entry_id: str):
    return next((e for e in entries if e.get("id") == entry_id), None)


def cmd_approve(args) -> int:
    entries = load_entries()
    entry = _find(entries, args.entry_id)
    if entry is None:
        print(f"no memory entry {args.entry_id}")
        return 1
    if entry.get("state") != "pending-approval":
        print(f"{args.entry_id} is in state '{entry.get('state', 'candidate')}', not pending-approval.")
        print("Only an entry that has met the criteria and been proposed can be approved.")
        return 1

    entry["scope"] = "shared"
    entry["state"] = "approved"
    entry["promotedAt"] = utc_now()
    entry["approvedBy"] = args.by
    entry["approvalNote"] = args.note or ""
    save_entries(entries)

    request = approval_request_path(args.entry_id)
    if request.exists():
        request.unlink()

    print(f"APPROVED {args.entry_id} — {entry['title']}")
    print(f"  approved by {args.by}")
    print("  This is now organizational guidance. It syncs to every connected repository")
    print("  and is injected into future sessions in all of them.")
    return 0


def cmd_reject(args) -> int:
    entries = load_entries()
    entry = _find(entries, args.entry_id)
    if entry is None:
        print(f"no memory entry {args.entry_id}")
        return 1

    entry["state"] = "rejected"
    entry["rejectedAt"] = utc_now()
    entry["rejectionReason"] = args.reason
    # Rejection is durable. Without it the entry keeps meeting the criteria and gets
    # re-proposed on every promote run, which trains the reviewer to stop reading.
    save_entries(entries)

    request = approval_request_path(args.entry_id)
    if request.exists():
        request.unlink()

    print(f"REJECTED {args.entry_id} — {entry['title']}")
    print(f"  reason: {args.reason}")
    print("  It stays repo-scoped and will not be proposed again. The reason is kept so")
    print("  the next person can see this was decided rather than overlooked.")
    return 0


def cmd_retire(args) -> int:
    entries = load_entries()
    entry = _find(entries, args.entry_id)
    if entry is None:
        print(f"no memory entry {args.entry_id}")
        return 1

    was_shared = entry.get("scope") == "shared"
    entry["state"] = "retired"
    entry["scope"] = "repo"
    entry["retiredAt"] = utc_now()
    entry["retirementReason"] = args.reason
    save_entries(entries)

    print(f"RETIRED {args.entry_id} — {entry['title']}")
    print(f"  reason: {args.reason}")
    if was_shared:
        print("  It no longer loads in any repository. The entry is kept rather than deleted:")
        print("  what the organization believed, and when it stopped, is part of the record.")
    return 0


def cmd_pending(args) -> int:
    entries = load_entries()
    pending = [e for e in entries if e.get("state") == "pending-approval"]
    if not pending:
        print("Nothing awaiting approval.")
        return 0
    print(f"{len(pending)} entr(ies) awaiting a human decision:\n")
    for entry in pending:
        print(f"  {entry['id']}  {entry['title']}")
        print(f"    since {entry.get('pendingSince')} · confidence {effective_confidence(entry):.2f}"
              f" · repos {', '.join(entry.get('seenInRepos', []))}")
        print(f"    artifact: {approval_request_path(entry['id']).relative_to(ROOT)}")
    return 0


def cmd_prune(args) -> int:
    entries = load_entries()
    now = datetime.now(timezone.utc)
    candidates = []
    for entry in entries:
        confidence = effective_confidence(entry, now)
        stamp = entry.get("lastReinforced") or entry.get("firstObserved") or ""
        try:
            last = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            cold_days = (now - last).days
        except ValueError:
            cold_days = 0
        if confidence < 0.3 and cold_days > 180:
            candidates.append((entry, confidence, cold_days))

    if not candidates:
        print("Nothing below 0.3 confidence and cold for 180 days.")
        return 0

    print(f"{len(candidates)} prune candidate(s):\n")
    for entry, confidence, cold in candidates:
        print(f"  {entry['title']}  (confidence {confidence:.2f}, cold {cold}d)")

    if not args.yes:
        print("\nInteractive by default and never silent. Re-run with --yes to remove these.")
        return 0

    keep = [e for e in entries if e not in [c[0] for c in candidates]]
    save_entries(keep)
    print(f"\nRemoved {len(candidates)} entr(ies).")
    return 0


def cmd_review(args) -> int:
    """Triage the candidates the learning-capture hook wrote during sessions."""
    candidates_file = SESSIONS / "learning-candidates.jsonl"
    if not candidates_file.exists():
        print("No learning candidates captured yet.")
        return 0
    lines = [line for line in candidates_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        print("No learning candidates captured yet.")
        return 0
    print(f"{len(lines)} candidate(s) awaiting triage:\n")
    for index, line in enumerate(lines, start=1):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        print(f"  {index}. [{candidate.get('kind')}] {candidate.get('title', '')[:110]}")
        print(f"     repo {candidate.get('repo')} · {candidate.get('capturedAt')}")
    print("\nA turn-level heuristic does not get direct write access to shared memory.")
    print("Capture the ones worth keeping explicitly:")
    print('  python scripts/memory.py capture --type <t> --title "..." --resolution "..."')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrator memory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("capture")
    p.add_argument("--type", required=True, choices=list(CATEGORY_FILES))
    p.add_argument("--title", required=True)
    p.add_argument("--context", default="")
    p.add_argument("--resolution", default="")
    p.add_argument("--applies-to", default="all")
    p.add_argument("--repo", default=None)
    p.add_argument("--allow-medium", action="store_true",
                   help="permit MEDIUM-tier redaction findings on an unattended write. "
                        "HIGH and injection markers are never permitted.")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("digest")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("promote", help="propose entries that meet the criteria for human approval")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("pending", help="entries awaiting a human decision")
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("approve", help="promote a candidate into shared memory")
    p.add_argument("entry_id")
    p.add_argument("--by", required=True, help="who is approving — this is recorded")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="refuse a candidate durably, so it is not re-proposed")
    p.add_argument("entry_id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("retire", help="withdraw an approved entry from shared memory")
    p.add_argument("entry_id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_retire)

    p = sub.add_parser("prune")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_prune)

    p = sub.add_parser("review")
    p.set_defaults(func=cmd_review)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
