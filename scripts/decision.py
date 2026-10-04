#!/usr/bin/env python3
"""
Decision memory: an append-only, event-sourced log of what was decided and why.

  python scripts/decision.py log --decision "..." --rationale "..." [--alternatives "..."] [--adr path]
  python scripts/decision.py list [--all]
  python scripts/decision.py search "<query>"
  python scripts/decision.py supersede <id> --decision "..." --rationale "..."
  python scripts/decision.py redact <id> --reason "..."
  python scripts/decision.py active            # the computed active set

THE GAP THIS CLOSES
-------------------
Three memory tiers store facts and patterns. None stored DECISIONS, and that matters
more here than in most systems because `architecture-decision` is a first-class skill
whose output is a file at `docs/adr/NNNN-slug.md` — which nothing ever read again.

The observable consequence: an agent in session 40 re-proposes the option session 12
explicitly rejected, because the rejection lives in a Markdown file in a folder no skill
loads. The ADR itself says "the rejected alternatives are the part a future reader
actually needs" and then provides no mechanism for a future reader to find them.

WHY EVENT-SOURCED
-----------------
This is an append-only event log, not mutable rows. `decide`, `supersede`, `redact`.
"Active" is COMPUTED — a `decide` whose id is not later referenced by a `supersede` or a
`redact`. A mutable `status` field would contradict append-only, and the whole value of
the log is that you can see what was believed at the time, not just what is believed now.

FREE TEXT IS GUARDED ON WRITE
------------------------------
Stored decisions are re-injected into future prompts, which makes this store an
injection surface as well as a storage surface. Every free-text field is scanned for
injection markers and HIGH-tier secrets, and the write is refused rather than sanitized.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, budgets, guard_free_text, repo_slug, utc_now  # noqa: E402

DECISIONS = ROOT / "memory" / "decisions"


def log_path(repo: str | None = None) -> Path:
    DECISIONS.mkdir(parents=True, exist_ok=True)
    return DECISIONS / f"{repo or repo_slug(Path.cwd())}.jsonl"


def read_events(path: Path) -> list:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def next_id(events: list) -> str:
    return f"d-{len([e for e in events if e.get('kind') == 'decide']) + 1:04x}"


def active_decisions(events: list) -> list:
    """Computed, never stored. A decide whose id is not superseded or redacted."""
    retired = {
        e.get("supersedes") for e in events
        if e.get("kind") in ("supersede", "redact") and e.get("supersedes")
    }
    return [e for e in events if e.get("kind") == "decide" and e["id"] not in retired]


def cmd_log(args) -> int:
    path = log_path(args.repo)
    events = read_events(path)

    # Same rule as the memory store, for the same two reasons: the decision log is
    # re-injected as context in future sessions, and it is written from hooks and CI
    # where an unattended "confirm" would silently mean "proceed".
    allow_medium = bool(getattr(args, "allow_medium", False))
    try:
        guard_free_text("decision", args.decision, interactive=allow_medium or None)
        guard_free_text("rationale", args.rationale or "", interactive=allow_medium or None)
        guard_free_text("alternatives_considered", args.alternatives or "",
                        interactive=allow_medium or None)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        print("Nothing was written. Stored decisions are re-read as context in future sessions.")
        return 3

    event = {
        "id": next_id(events),
        "kind": "decide",
        "decision": args.decision,
        "rationale": args.rationale or "",
        "alternatives_considered": args.alternatives or "",
        "scope": args.scope,
        "date": utc_now(),
        "source": args.source,
        "confidence": args.confidence,
        "adr": args.adr or None,
    }
    append_event(path, event)

    print(f"Logged {event['id']}: {event['decision'][:90]}")
    print(f"  {path.relative_to(ROOT)}")
    if not args.adr:
        print("\n  No --adr path. That is allowed for a small decision, but for an architecture")
        print("  choice the ADR is where the rejected options live — and those are the part a")
        print("  future reader actually needs.")
    if not args.alternatives:
        print("\n  No --alternatives recorded. A decision with no stated alternative is hard to")
        print("  revisit: the next reader cannot tell what was considered and rejected from what")
        print("  was never considered at all.")
    return 0


def cmd_list(args) -> int:
    path = log_path(args.repo)
    events = read_events(path)
    if not events:
        print(f"No decisions recorded for {path.stem}.")
        return 0
    shown = events if args.all else active_decisions(events)
    label = "all events" if args.all else "active decisions"
    print(f"{len(shown)} {label} in {path.name}\n")
    for event in shown:
        kind = event.get("kind", "decide")
        marker = {"decide": " ", "supersede": "~", "redact": "x"}.get(kind, "?")
        print(f"  [{marker}] {event.get('id','?')}  {event.get('decision', event.get('reason',''))[:88]}")
        if event.get("rationale"):
            print(f"        why: {event['rationale'][:88]}")
        if event.get("alternatives_considered"):
            print(f"        rejected: {event['alternatives_considered'][:88]}")
        if event.get("adr"):
            print(f"        adr: {event['adr']}")
    return 0


def cmd_active(args) -> int:
    events = read_events(log_path(args.repo))
    active = active_decisions(events)
    cap = budgets().get("memoryRead", {}).get("maxInjectedDecisions", 8)
    if not active:
        print("_No active decisions on this repo._")
        return 0
    selected = active[-cap:]
    print(f"## Settled decisions ({len(selected)} of {len(active)})\n")
    for event in selected:
        print(f"- `{event['id']}` **{event['decision']}**")
        if event.get("rationale"):
            print(f"  — {event['rationale']}")
    if len(active) > cap:
        print(f"\n_{len(active) - cap} older decisions not shown (cap {cap})._")
    print("\n_Treat each as settled, with its rationale. If you are about to reverse one,_")
    print("_say so explicitly and say why._")
    return 0


def cmd_search(args) -> int:
    events = read_events(log_path(args.repo))
    query = args.query.lower()
    hits = [
        e for e in events
        if query in json.dumps(e, ensure_ascii=False).lower()
    ]
    if not hits:
        print(f"No decision mentions '{args.query}'.")
        print("That is a real answer: it means the question has not been settled here.")
        return 0
    retired = {e.get("supersedes") for e in events if e.get("supersedes")}
    print(f"{len(hits)} match(es):\n")
    for event in hits:
        state = "SUPERSEDED" if event.get("id") in retired else event.get("kind", "decide").upper()
        print(f"  [{state}] {event.get('id')}  {event.get('decision', '')[:88]}")
        if event.get("rationale"):
            print(f"           why: {event['rationale'][:88]}")
        if event.get("adr"):
            print(f"           adr: {event['adr']}")
    return 0


def cmd_supersede(args) -> int:
    path = log_path(args.repo)
    events = read_events(path)
    if not any(e.get("id") == args.old_id for e in events):
        print(f"no decision {args.old_id} in {path.name}")
        return 1
    try:
        guard_free_text("decision", args.decision)
        guard_free_text("rationale", args.rationale or "")
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 3

    event = {
        "id": next_id(events),
        "kind": "supersede",
        "supersedes": args.old_id,
        "decision": args.decision,
        "rationale": args.rationale or "",
        "scope": args.scope,
        "date": utc_now(),
        "source": args.source,
    }
    append_event(path, event)
    print(f"{event['id']} supersedes {args.old_id}.")
    print("  The original event stays in the log. What was believed at the time is part of")
    print("  the record — that is the point of an append-only store.")
    return 0


def cmd_redact(args) -> int:
    path = log_path(args.repo)
    events = read_events(path)
    if not any(e.get("id") == args.target_id for e in events):
        print(f"no decision {args.target_id}")
        return 1
    append_event(path, {
        "id": next_id(events),
        "kind": "redact",
        "supersedes": args.target_id,
        "reason": args.reason,
        "date": utc_now(),
    })
    print(f"{args.target_id} redacted: {args.reason}")
    print("  Redaction removes it from the ACTIVE set. It does not delete the original line —")
    print("  if the original contains something that must not exist, edit the file directly and")
    print("  say so, because the chain will show the edit.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Decision memory")
    parser.add_argument("--repo", default=None, help="repo slug (defaults to the cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("log")
    p.add_argument("--decision", required=True)
    p.add_argument("--rationale", default="")
    p.add_argument("--alternatives", default="")
    p.add_argument("--scope", default="repo", choices=["repo", "org"])
    p.add_argument("--source", default="agent", choices=["agent", "human"])
    p.add_argument("--confidence", type=int, default=8)
    p.add_argument("--adr", default=None)
    p.add_argument("--allow-medium", action="store_true",
                   help="permit MEDIUM-tier redaction findings on an unattended write. "
                        "HIGH and injection markers are never permitted.")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("list"); p.add_argument("--all", action="store_true"); p.set_defaults(func=cmd_list)
    sub.add_parser("active").set_defaults(func=cmd_active)
    p = sub.add_parser("search"); p.add_argument("query"); p.set_defaults(func=cmd_search)

    p = sub.add_parser("supersede")
    p.add_argument("old_id")
    p.add_argument("--decision", required=True)
    p.add_argument("--rationale", default="")
    p.add_argument("--scope", default="repo")
    p.add_argument("--source", default="agent")
    p.set_defaults(func=cmd_supersede)

    p = sub.add_parser("redact")
    p.add_argument("target_id"); p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_redact)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
