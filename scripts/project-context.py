#!/usr/bin/env python3
"""
The project context: what the orchestrator understands about the application.

  python scripts/project-context.py scaffold --name "Donation Platform"
  python scripts/project-context.py status
  python scripts/project-context.py check
  python scripts/project-context.py questions

TWO ARTIFACTS, AND CONFLATING THEM IS THE MISTAKE
--------------------------------------------------
  knowledge/   the SOURCE OF RECORD. Citable. "What does the SOW say about retention?"
               answered with an anchor back to page 14. Never interpreted, only extracted
               and curated.

  context/     the SYNTHESISED UNDERSTANDING. The domain model, the feature inventory,
               the screen flows, the business rules. What an agent reads before it writes
               a line of code.

The second is DERIVED from the first, by the BA, analyst and architect agents. Keeping
them separate matters because they rot differently: a source document is immutable and a
synthesis is a working hypothesis that gets corrected. Merging them produces a corpus
where nobody can tell which sentences the client actually wrote.

EVERY SYNTHESISED CLAIM CARRIES PROVENANCE
-------------------------------------------
A line in `context/` states what the system will be built to do, so it needs to say where
that came from:

    Donations may carry an optional impact-investment amount.
    <!-- from: knowledge/distilled/donations.md#impact-investment -->

`check` fails on a claim without one. Not pedantry: six weeks in, the only question that
matters about a requirement is whether the client said it or somebody inferred it, and by
then nobody remembers. A synthesis that cannot answer that is a set of assumptions
wearing a specification's clothes.

OPEN QUESTIONS ARE THE MOST VALUABLE FILE
------------------------------------------
`06-open-questions.md` is the primary output of a first pass, not a leftover. A brief
with no open questions after reading a client's first handover has not been read
carefully — it has been paraphrased.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import utc_now  # noqa: E402


def workspace() -> Path:
    override = os.environ.get("ORCHESTRATOR_WORKSPACE")
    return Path(override).resolve() if override else Path.cwd().resolve()


PROVENANCE = re.compile(r"<!--\s*from:\s*([^>]+?)\s*-->")
PLACEHOLDER = re.compile(r"_TO BE COMPLETED_|_not yet established_|TODO", re.IGNORECASE)

FILES = {
    "00-overview.md": ("Overview", """What the product is, who uses it, and what problem it solves — in the client's
own framing, not ours.

## What it is {#what-it-is}

_TO BE COMPLETED_

## Who uses it {#users}

| Role | What they do | Why they care |
|---|---|---|

## Success criteria {#success}

What the client would point at in six months to say this worked. If the documents do not
say, that is an open question rather than something to invent.

_TO BE COMPLETED_

## Explicitly out of scope {#out-of-scope}

The most expensive ambiguity in any project is the thing everybody assumed was included.
"""),

    "01-domain-model.md": ("Domain model", """The entities, their fields and their relationships. This is what the code will be
shaped like, so getting a name wrong here is expensive later.

## Entities {#entities}

| Entity | Description | Key fields | Source |
|---|---|---|---|

## Relationships {#relationships}

| From | Cardinality | To | Notes |
|---|---|---|---|

## Naming decisions {#naming}

Where the client's word and the obvious technical word differ, the CLIENT'S word wins and
is recorded here. A domain model that renames the business's vocabulary produces a
codebase nobody in the business can read back.
"""),

    "02-features.md": ("Features", """One row per feature, traceable to its source. This is the backlog's parent, not the
backlog itself.

## Feature inventory {#inventory}

| ID | Epic | Feature | Priority | Release | Source | Status |
|---|---|---|---|---|---|---|

## Dependencies between features {#dependencies}

What must ship before what, and why. A dependency discovered during implementation is a
sprint lost.

## Features mentioned but not specified {#underspecified}

Named in a document with no detail behind it. These are not backlog items yet, and
recording them here stops them being estimated as though they were.
"""),

    "03-screens.md": ("Screens", """The screen inventory and the flows between them, derived from the mockups.

## Screen inventory {#inventory}

| Screen | Purpose | Source | Fields described? |
|---|---|---|---|

## Flows {#flows}

How a user gets from one screen to another to accomplish something.

## Screens implied but not provided {#missing}

Every mockup implies screens nobody drew — error states, empty states, permission-denied,
confirmation. Listing them here is usually the single most useful output of a screen
review, because they are the ones discovered late.
"""),

    "04-business-rules.md": ("Business rules", """Rules the software must enforce. Each one needs a source; an invented business rule is
the most damaging kind of invention, because it looks like domain knowledge.

## Rules {#rules}

| ID | Rule | Applies to | Source | Confidence |
|---|---|---|---|---|

## Validation {#validation}

Field-level constraints: required, format, range, uniqueness.

## Calculations {#calculations}

Any arithmetic the business cares about, stated precisely — including rounding and
currency handling, which are where these go wrong.
"""),

    "05-integrations.md": ("Integrations", """External systems this application talks to.

## Systems {#systems}

| System | Direction | Protocol | Auth | Owner | Source |
|---|---|---|---|---|---|

## Data ownership {#ownership}

Which system is the source of truth for each entity. Two systems both believing they own
a record is the defect that surfaces in production and never in test.
"""),

    "06-open-questions.md": ("Open questions", """**The most valuable file here.** A brief with no open questions after a first handover
has been paraphrased, not read.

## Blocking {#blocking}

Cannot start the affected work without an answer.

| # | Question | Blocks | Asked of | Asked on | Status |
|---|---|---|---|---|---|

## Non-blocking {#non-blocking}

Worth asking, but there is a defensible assumption to proceed on. **State the assumption**
— an unstated assumption is indistinguishable from a fact three weeks later.

| # | Question | Working assumption | Asked of | Status |
|---|---|---|---|---|

## Contradictions between sources {#contradictions}

Where two documents disagree. Record both with their dates; do not silently prefer the
newer one. This is the highest-value content in the whole corpus.

| # | Topic | Source A | Source B | Resolution |
|---|---|---|---|---|
"""),

    "07-decisions.md": ("Decisions", """Decisions taken about this project, with rationale. Joined to the decision log so an
agent in four months does not re-propose what was rejected in week one.

## Decisions {#decisions}

| ID | Decision | Rationale | Rejected alternative | Date | ADR |
|---|---|---|---|---|---|

Record each one durably too:

```
python scripts/decision.py log --decision "..." --rationale "..." --alternatives "..."
```
"""),
}

BANNER = """<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->
"""


SEPARATOR = re.compile(r"^\|[\s\-:|]+\|$")


def count_data_rows(body: str) -> list:
    """
    Count real content rows across ALL tables in a file.

    The naive version — take every pipe line and drop the first — is wrong the moment a
    file holds more than one table, because every subsequent table's HEADER counts as
    data. These templates all carry several tables, so that error reported an empty
    scaffold as partly filled and made `check` fire on content nobody had written yet.
    A validator that cries wolf on an untouched template is one people learn to ignore.

    So: walk the lines, treat each contiguous run of pipe lines as its own table, and
    skip that table's header.
    """
    rows, in_table, seen_header = [], False, False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table, seen_header = False, False
            continue
        if SEPARATOR.match(stripped):
            continue
        if not in_table:
            in_table, seen_header = True, True
            continue                       # this is the header of a new table
        if stripped.strip("| ").strip():
            rows.append(stripped)
    return rows


def context_dir() -> Path:
    return workspace() / "context"


def cmd_scaffold(args) -> int:
    root = context_dir()
    root.mkdir(parents=True, exist_ok=True)
    created, existing = [], []

    for filename, (title, body) in FILES.items():
        path = root / filename
        if path.exists() and not args.force:
            existing.append(filename)
            continue
        path.write_text(f"{BANNER}\n# {title}\n\n{body}", encoding="utf-8")
        created.append(filename)

    readme = root / "README.md"
    if not readme.exists() or args.force:
        readme.write_text(f"""# Project context — {args.name or workspace().name}

What the orchestrator understands about this application. Synthesised from
`knowledge/distilled/`, never authored from scratch.

## The two artifacts

| | `knowledge/` | `context/` |
|---|---|---|
| What | source of record | synthesised understanding |
| Authored by | the client | our agents, from the client's documents |
| Edited? | never — immutable once extracted | continuously, as understanding improves |
| Answers | "what does the SOW say?" | "what are we building?" |

## How it is produced

```
knowledge/inbox/        client documents, exactly as received
   -> extract           mechanical; images become stubs a model must describe
knowledge/extracted/
   -> distil            curated BY TOPIC, provenance on every claim
knowledge/distilled/
   -> /project-brief    BA + analyst + architect synthesise
context/                <- you are here
```

## Rules

1. **Every claim carries provenance.** `<!-- from: knowledge/distilled/x.md#anchor -->`.
   `project-context.py check` fails without it.
2. **No source means it is an assumption.** It belongs in `06-open-questions.md` with the
   assumption written down, not here where it reads as a requirement.
3. **Open questions are output, not failure.** A first pass with none has been
   paraphrased rather than read.
4. **Contradictions are recorded, never resolved silently.** Two documents disagreeing is
   the most valuable signal the corpus contains.

## Files

| File | Holds |
|---|---|
| `00-overview.md` | what the product is, who uses it, what is out of scope |
| `01-domain-model.md` | entities, fields, relationships, naming decisions |
| `02-features.md` | the feature inventory and what is under-specified |
| `03-screens.md` | screen inventory, flows, and the screens nobody drew |
| `04-business-rules.md` | rules, validation, calculations |
| `05-integrations.md` | external systems and who owns which data |
| `06-open-questions.md` | blocking, non-blocking, and contradictions |
| `07-decisions.md` | what was decided and what was rejected |

Generated {utc_now()}.
""", encoding="utf-8")
        created.append("README.md")

    provenance = root / "_provenance.json"
    if not provenance.exists() or args.force:
        provenance.write_text(json.dumps({
            "project": args.name or workspace().name,
            "scaffoldedAt": utc_now(),
            "sourceOfTruth": "knowledge/distilled/",
            "note": (
                "context/ is derived. If a claim here and the knowledge base disagree, the "
                "knowledge base wins and the context is corrected — never the other way "
                "round, because the knowledge base is what the client actually wrote."
            ),
            "batches": [],
        }, indent=2) + "\n", encoding="utf-8")
        created.append("_provenance.json")

    print(f"Project context at {root}\n")
    for name in created:
        print(f"  created  {name}")
    for name in existing:
        print(f"  kept     {name}  (--force to overwrite)")
    print("\nNext: run /project-brief in Claude Code to have the agents fill it from")
    print("knowledge/distilled/. Do not fill it by hand from the raw documents — the")
    print("distillation step is where contradictions get caught.")
    return 0


def scan() -> dict:
    root = context_dir()
    if not root.is_dir():
        return {}
    report = {}
    for filename in FILES:
        path = root / filename
        if not path.exists():
            report[filename] = {"exists": False}
            continue
        text = path.read_text(encoding="utf-8")
        body = text.split("-->", 1)[-1]
        data_rows = count_data_rows(body)
        report[filename] = {
            "exists": True,
            "placeholders": len(PLACEHOLDER.findall(body)),
            "provenance": len(PROVENANCE.findall(body)),
            "tableRows": len(data_rows),
            "bytes": len(body.encode("utf-8")),
        }
    return report


def cmd_status(args) -> int:
    report = scan()
    if not report:
        print(f"No context/ in {workspace()}. Run `scaffold` first.")
        return 1
    print(f"Project context — {workspace().name}\n")
    print(f"  {'file':<26}{'rows':>6}{'cited':>7}{'todo':>6}  state")
    print("  " + "-" * 58)
    for name, info in report.items():
        if not info["exists"]:
            print(f"  {name:<26}{'-':>6}{'-':>7}{'-':>6}  MISSING")
            continue
        state = ("empty" if info["tableRows"] == 0 and info["placeholders"] else
                 "drafted" if info["placeholders"] else "complete")
        print(f"  {name:<26}{info['tableRows']:>6}{info['provenance']:>7}"
              f"{info['placeholders']:>6}  {state}")

    total_rows = sum(i.get("tableRows", 0) for i in report.values())
    total_cited = sum(i.get("provenance", 0) for i in report.values())
    print(f"\n  {total_rows} populated row(s), {total_cited} provenance citation(s)")
    if total_rows and not total_cited:
        print("\n  Content with no provenance at all. Every claim here should name the")
        print("  distilled topic it came from, or be moved to open questions as an assumption.")
    return 0


def cmd_check(args) -> int:
    root = context_dir()
    if not root.is_dir():
        print(f"No context/ in {workspace()}.")
        return 1

    problems = []
    for filename in FILES:
        path = root / filename
        if not path.exists():
            problems.append((filename, "missing"))
            continue
        body = path.read_text(encoding="utf-8").split("-->", 1)[-1]
        data_rows = count_data_rows(body)
        citations = PROVENANCE.findall(body)

        if data_rows and not citations and filename not in ("06-open-questions.md", "07-decisions.md"):
            problems.append((filename,
                             f"{len(data_rows)} populated row(s) and no provenance citation. "
                             f"Every synthesised claim must name its distilled source."))

        for source in citations:
            target = workspace() / source.split("#")[0]
            if not target.exists():
                problems.append((filename, f"provenance points at a file that does not exist: {source}"))

    questions = root / "06-open-questions.md"
    if questions.exists():
        body = questions.read_text(encoding="utf-8").split("-->", 1)[-1]
        if len(count_data_rows(body)) == 0:
            problems.append(("06-open-questions.md",
                             "no open questions recorded. A brief produced from a client's first "
                             "handover with zero open questions has been paraphrased, not read. "
                             "If there genuinely are none, say so explicitly in the file."))

    print(f"Context check — {workspace().name}\n")
    if not problems:
        print("  OK. Every claim is cited, every citation resolves, questions are recorded.")
        return 0
    for filename, issue in problems:
        print(f"  {filename}")
        print(f"    {issue}")
    print(f"\n{len(problems)} problem(s).")
    return 1


def cmd_questions(args) -> int:
    path = context_dir() / "06-open-questions.md"
    if not path.exists():
        print("No 06-open-questions.md. Run `scaffold` first.")
        return 1
    print(path.read_text(encoding="utf-8").split("-->", 1)[-1].strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Project context")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scaffold")
    p.add_argument("--name"); p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_scaffold)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("questions").set_defaults(func=cmd_questions)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
