#!/usr/bin/env python3
"""
Knowledge ingestion: turn a pile of client documents into something that can be cited.

  python scripts/ingest-knowledge.py extract        # inbox/ -> extracted/
  python scripts/ingest-knowledge.py index          # distilled/ -> index/
  python scripts/ingest-knowledge.py search "<q>"
  python scripts/ingest-knowledge.py topics
  python scripts/ingest-knowledge.py show <anchor>
  python scripts/ingest-knowledge.py status

WHY A PIPELINE RATHER THAN A CONTEXT DUMP
------------------------------------------
The naive approach is to load the documents into context and let the model sort it out.
That fails three ways, each with a different fix:

  1. It blows the budget. A 40-page specification is roughly 25,000 tokens; five of them
     is most of a window, spent before anyone asks a question.
  2. It cannot be cited. "The spec says X" with no anchor is exactly the failure the
     grounding contract exists to prevent, imported from a different domain.
  3. Contradictions vanish. Two documents disagreeing about a retention period is the
     most valuable signal in the corpus, and flattening them into one window makes the
     model silently pick one.

FOUR STAGES, AND THE FIRST TWO ARE IMMUTABLE
---------------------------------------------
  inbox/      source documents exactly as received. Never edited.
  extracted/  mechanical extraction, page markers preserved. Never hand-patched — if
              extraction is wrong, fix the extractor and re-run. A hand-patched
              extraction no longer corresponds to its source, and once that is true of
              one file, no citation in the corpus can be trusted.
  distilled/  curated BY TOPIC, not by document, with provenance on every claim.
  index/      the retrieval index. Only this and the topic headings load eagerly.

PDF EXTRACTION
--------------
Text-layer PDFs are extracted natively. Scanned PDFs need OCR, which is not a dependency
this repository takes — the file is listed as needing manual handling rather than
silently producing an empty document that looks successfully ingested.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, budgets, redact_scan, utc_now, write_json, read_json  # noqa: E402

def _workspace() -> Path:
    """
    Where WRITES go: the current working directory, never the plugin.

    Extraction and indexing always target the directory you are standing in. The plugin
    is installed once per machine and shared by every repository that has it, so a write
    into the plugin root from one repo would edit every repo's corpus at once.

    READS are different, and deliberately so. When the current repository has no
    distilled knowledge of its own, read-only commands fall back to the corpus that
    ships inside the plugin — see _fallback_to_plugin_if_empty. That is what lets a
    developer cite the same knowledge base from any repository instead of each one
    carrying a copy that drifts, and the fallback announces itself rather than answering
    silently from a corpus the reader did not expect.

    The cost of that choice, stated so nobody has to rediscover it: the shared corpus is
    not scoped to one project. With a second client's material present, a query for "the
    retention period" would match both clients' contracts and nothing here separates
    them. Revisit this before ingesting a second client.

    Override with --workspace for a repository you are not standing in.
    """
    override = os.environ.get("ORCHESTRATOR_WORKSPACE")
    return Path(override).resolve() if override else Path.cwd().resolve()


KNOWLEDGE = _workspace() / "knowledge"
INBOX = KNOWLEDGE / "inbox"
EXTRACTED = KNOWLEDGE / "extracted"
DISTILLED = KNOWLEDGE / "distilled"
INDEX = KNOWLEDGE / "index"
INDEX_FILE = INDEX / "knowledge-index.json"


# Commands that only read. These may fall back to the plugin's shared knowledge base;
# extract and index must never write into the plugin from a consumer repo, because the
# plugin is shared machine-wide and a write there would edit every repo's corpus at once.
READ_ONLY_COMMANDS = {"topics", "status", "worklist", "search", "show"}


def _rebind(workspace: Path) -> None:
    """Re-point every path at an explicit workspace. Called once from main()."""
    global KNOWLEDGE, INBOX, EXTRACTED, DISTILLED, INDEX, INDEX_FILE
    KNOWLEDGE = workspace / "knowledge"
    INBOX = KNOWLEDGE / "inbox"
    EXTRACTED = KNOWLEDGE / "extracted"
    DISTILLED = KNOWLEDGE / "distilled"
    INDEX = KNOWLEDGE / "index"
    INDEX_FILE = INDEX / "knowledge-index.json"

from _extractors import (  # noqa: E402
    dispatch as extract_dispatch,
    IMAGE_SUFFIXES, HTML_SUFFIXES, LEGACY_SUFFIXES, TEXT_SUFFIXES,
)




def cmd_extract(args) -> int:
    for directory in (INBOX, EXTRACTED, DISTILLED, INDEX):
        directory.mkdir(parents=True, exist_ok=True)

    sources = [p for p in sorted(INBOX.rglob("*")) if p.is_file() and not p.name.startswith(".")]
    if not sources:
        print(f"No files in {INBOX}. Drop the client documents there first.")
        return 0

    extracted, skipped, refused, stubs, preserved = [], [], [], [], []
    for source in sources:
        rel = source.relative_to(INBOX)
        target = EXTRACTED / rel.with_suffix(".md")
        suffix = source.suffix.lower()

        # A DESCRIBED IMAGE IS NOT RE-STUBBED.
        #
        # Everything else here is reproducible from its source, which is why the header says
        # DO NOT EDIT: re-running extract must converge on the same bytes. An image stub is
        # the one exception, because a script cannot produce its content — a model looked at
        # the screen and wrote the fields, states and navigation by hand.
        #
        # Without this guard, `extract` is destructive rather than idempotent: adding one new
        # document to the inbox silently overwrites every completed screen description with a
        # fresh stub. The loss is quiet — worklist goes back to "6 awaiting description" and
        # nothing says the work existed.
        #
        # Re-describe a screen by deleting its .md and re-running, which makes the overwrite
        # deliberate instead of incidental.
        if suffix in IMAGE_SUFFIXES and target.exists():
            existing = target.read_text(encoding="utf-8", errors="replace")
            if "status: awaiting-description" not in existing:
                preserved.append(rel.as_posix())
                continue

        text, note = extract_dispatch(source)

        if text is None:
            skipped.append((rel.as_posix(), note))
            continue

        # Redaction runs on the way IN. Client documents carry names, contract values,
        # and occasionally a credential in an appendix nobody remembered was there.
        findings = redact_scan(text, str(source))
        high = [f for f in findings if f["tier"] == "HIGH"]
        if high:
            refused.append((rel.as_posix(), [f["id"] for f in high]))
            continue

        medium = [f for f in findings if f["tier"] == "MEDIUM" and f["autoRedactable"]]
        for finding in sorted(medium, key=lambda f: -f["start"]):
            head, tail = text[:finding["start"]], text[finding["start"]:]
            text = head + tail.replace(finding["span"], finding["redactToken"], 1)

        header = (
            f"<!-- EXTRACTED from knowledge/inbox/{rel.as_posix()} on {utc_now()} -->\n"
            f"<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A\n"
            f"     hand-patched extraction no longer matches its source, and once that is\n"
            f"     true of one file no citation in this corpus can be trusted. -->\n"
        )
        if note:
            header += f"<!-- extraction note: {note} -->\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(header + "\n" + text, encoding="utf-8")
        extracted.append((rel.as_posix(), len(text), len(medium)))

    print(f"Extracted {len(extracted)} document(s) to {EXTRACTED}/\n")
    for name, size, redactions in extracted:
        note = f"  ({redactions} auto-redacted)" if redactions else ""
        print(f"  {name:<50} {size:>9,} chars{note}")

    if refused:
        print(f"\nREFUSED {len(refused)} document(s) — HIGH-tier secrets present:")
        for name, ids in refused:
            print(f"  {name}: {', '.join(ids)}")
        print("  Remove the credential from the source, or handle these outside the corpus.")

    if skipped:
        print(f"\nNot extracted ({len(skipped)}) — listed rather than silently skipped:")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    if preserved:
        print(f"\nPreserved {len(preserved)} completed image description(s) — not re-stubbed:")
        for name in preserved[:15]:
            print(f"  {name}")
        print("  Delete the .md and re-run to describe one again.")

    if stubs:
        print(f"\n{len(stubs)} image(s) need a model to describe them — they are STUBS, not extractions:")
        for name in stubs[:15]:
            print(f"  {name}")
        print("  Run `python scripts/ingest-knowledge.py worklist` for the full list.")

    print(f"\nNext: curate {EXTRACTED}/ into {DISTILLED}/ by TOPIC,")
    print("then run `python scripts/ingest-knowledge.py index`.")
    print("Distil by topic, not by document — mirroring the filing cabinet reproduces the")
    print("filing cabinet's retrieval problem, which is the problem you were solving.")
    return 0


ANCHOR = re.compile(r"^(#{2,4})\s+(.+?)\s*\{#([a-z0-9-]+)\}\s*$", re.MULTILINE)
SOURCE_COMMENT = re.compile(r"<!--\s*source:\s*([^>]+?)\s*-->")
CONFLICT = re.compile(r"⚠️\s*\*\*Conflict", re.IGNORECASE)


def cmd_index(args) -> int:
    INDEX.mkdir(parents=True, exist_ok=True)
    if not DISTILLED.is_dir():
        print(f"{DISTILLED} does not exist yet.")
        return 1

    topics, warnings = [], []
    for path in sorted(DISTILLED.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(KNOWLEDGE).as_posix()
        headings = ANCHOR.findall(text)
        if not headings:
            warnings.append(f"{rel}: no anchored headings. Add `{{#anchor}}` — anchors are what "
                            f"a citation points at, and an unanchored document cannot be cited.")
        sources = SOURCE_COMMENT.findall(text)
        if not sources:
            warnings.append(f"{rel}: no `<!-- source: -->` provenance. A distilled document with "
                            f"no traceable source is a summary somebody will treat as authoritative.")
        for _, title, anchor in headings:
            section = text.split(f"{{#{anchor}}}", 1)[-1]
            end = section.find("\n## ")
            body = section[:end] if end != -1 else section
            topics.append({
                "topic": title.strip(),
                "anchor": anchor,
                "file": rel,
                "citation": f"{rel}#{anchor}",
                "sources": SOURCE_COMMENT.findall(body) or sources,
                "hasConflict": bool(CONFLICT.search(body)),
                "bytes": len(body.encode("utf-8")),
                "keywords": sorted(set(
                    w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", f"{title} {body[:600]}")
                ))[:25],
            })

    # THE EAGER DIGEST IS THE DOCUMENT LIST, NOT THE TOPIC LIST.
    #
    # This measured the topic list once, and on the first real corpus (44 client documents,
    # 236 anchors) it produced a 21,553B digest against a 1,000B cap — larger than the entire
    # 18,000-char eager allocation in config/token-budgets.json:22. Neither escape was right:
    # consolidating anchors would coarsen every citation, and provenance is the whole point of
    # this corpus, while raising the cap to fit would spend the eager budget on a table of
    # contents before the user typed anything.
    #
    # The digest was measuring the wrong thing. What has to load eagerly is enough to know
    # WHICH document answers a question; the anchors within it are what `search` and `show`
    # retrieve on demand. That is the progressive-disclosure rule this repository already
    # applies to skills/*/references/, applied here.
    #
    # Growth is now bounded by document count rather than anchor count, so a corpus can be
    # curated at whatever granularity serves it without the eager surface tracking that
    # granularity.
    digest_cap = budgets().get("eager", {}).get("layers", {}).get("knowledgeDigest", 1000)
    documents = sorted({t["file"] for t in topics})
    digest_lines = {
        doc: sum(1 for t in topics if t["file"] == doc) for doc in documents
    }
    digest_bytes = sum(
        len(f"- {doc} ({count} topics)\n".encode("utf-8"))
        for doc, count in digest_lines.items()
    )

    write_json(INDEX_FILE, {
        "version": 1,
        "builtAt": utc_now(),
        "topicCount": len(topics),
        "documentCount": len(documents),
        "conflictCount": sum(1 for t in topics if t["hasConflict"]),
        "digestBytes": digest_bytes,
        "digestCap": digest_cap,
        "digest": [f"{doc} ({count} topics)" for doc, count in digest_lines.items()],
        "topics": topics,
    })

    print(f"Indexed {len(topics)} topic(s) across "
          f"{len({t['file'] for t in topics})} document(s).")
    print(f"  {INDEX_FILE}")
    conflicts = [t for t in topics if t["hasConflict"]]
    if conflicts:
        print(f"\n  {len(conflicts)} topic(s) carry an unresolved conflict — that is the most")
        print("  valuable content in the corpus. Do not let anyone quietly resolve them:")
        for topic in conflicts:
            print(f"    {topic['citation']}  {topic['topic']}")
    if digest_bytes > digest_cap:
        print(f"\n  Digest is {digest_bytes}B against a {digest_cap}B cap. The DOCUMENT list is")
        print("  what loads eagerly; anchors are retrieved on demand by `search` and `show`.")
        print("  Over cap means too many distilled documents, not too many anchors — merge")
        print("  topics that answer the same question, or raise knowledgeDigest deliberately.")
    if warnings:
        print(f"\n  {len(warnings)} curation warning(s):")
        for warning in warnings[:12]:
            print(f"    - {warning}")
    return 0


def load_index() -> dict | None:
    return read_json(INDEX_FILE)


def cmd_search(args) -> int:
    index = load_index()
    if not index:
        print("No index. Run `python scripts/ingest-knowledge.py index` first.")
        return 1
    query_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", args.query.lower()))
    scored = []
    for topic in index["topics"]:
        overlap = len(query_words & set(topic["keywords"]))
        title_hit = 3 if any(w in topic["topic"].lower() for w in query_words) else 0
        score = overlap + title_hit
        if score:
            scored.append((score, topic))
    if not scored:
        print(f"Nothing in the corpus matches '{args.query}'.")
        print("That is the answer. Do not fill the gap from general knowledge without saying so.")
        return 0
    scored.sort(key=lambda row: -row[0])
    print(f"{len(scored)} match(es):\n")
    for score, topic in scored[:args.limit]:
        flag = "  [CONFLICT]" if topic["hasConflict"] else ""
        print(f"  [{score}] {topic['topic']}{flag}")
        print(f"        cite: {topic['citation']}")
        print(f"        from: {', '.join(topic['sources'][:3]) or 'no source recorded'}")
    return 0


def cmd_topics(args) -> int:
    index = load_index()
    if not index:
        print("No index yet.")
        return 1
    print(f"{index['topicCount']} topics across {index['documentCount']} documents "
          f"(built {index['builtAt']})\n")
    by_file = {}
    for topic in index["topics"]:
        by_file.setdefault(topic["file"], []).append(topic)
    for file, topics in sorted(by_file.items()):
        print(f"  {file}")
        for topic in topics:
            flag = "  [CONFLICT]" if topic["hasConflict"] else ""
            print(f"    #{topic['anchor']:<32} {topic['topic']}{flag}")
    return 0


def cmd_show(args) -> int:
    index = load_index()
    if not index:
        print("No index yet.")
        return 1
    anchor = args.anchor.lstrip("#")
    match = next((t for t in index["topics"] if t["anchor"] == anchor), None)
    if not match:
        print(f"No topic anchored '{anchor}'. Run `topics` to list them.")
        return 1
    path = KNOWLEDGE / match["file"]
    text = path.read_text(encoding="utf-8")
    section = text.split(f"{{#{anchor}}}", 1)[-1]
    end = section.find("\n## ")
    print(f"# {match['topic']}   ({match['citation']})\n")
    print(section[:end] if end != -1 else section)
    return 0


def cmd_status(args) -> int:
    counts = {
        "inbox": len([p for p in INBOX.rglob("*") if p.is_file()]) if INBOX.is_dir() else 0,
        "extracted": len(list(EXTRACTED.rglob("*.md"))) if EXTRACTED.is_dir() else 0,
        "distilled": len(list(DISTILLED.rglob("*.md"))) if DISTILLED.is_dir() else 0,
    }
    index = load_index()
    print("Knowledge base")
    print(f"  inbox      {counts['inbox']:>4} source document(s)")
    print(f"  extracted  {counts['extracted']:>4} document(s)")
    print(f"  distilled  {counts['distilled']:>4} curated topic document(s)")
    if index:
        print(f"  indexed    {index['topicCount']:>4} topic(s), "
              f"{index['conflictCount']} unresolved conflict(s), built {index['builtAt']}")
    else:
        print("  indexed       - (run `index`)")
    if counts["extracted"] and not counts["distilled"]:
        print("\n  Extraction is done and nothing is distilled. The extracted text is not the")
        print("  knowledge base — it is the raw material. Curate it by topic before querying.")
    return 0



def cmd_worklist(args) -> int:
    """
    What is in the corpus but not yet understood.

    Two kinds of unfinished work, and they are different jobs:
      - image stubs, which need a model to look at the screen
      - extracted documents with no distilled topic citing them, which need curation

    Both are reported rather than hidden. The failure this guards against is a corpus
    that looks complete because everything was "ingested", while half of it is stubs and
    the other half was never curated into anything answerable.
    """
    if not EXTRACTED.is_dir():
        print(f"{EXTRACTED} does not exist yet. Run `extract` first.")
        return 1

    stubs, done = [], []
    for path in sorted(EXTRACTED.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        (stubs if "status: awaiting-description" in text else done).append(path)

    index = load_index()
    cited = set()
    for topic in (index or {}).get("topics", []):
        for source in topic.get("sources", []):
            cited.add(pathlib.Path(str(source)).stem.lower())

    uncurated = [p for p in done if p.stem.lower() not in cited]

    print("Knowledge worklist\n")
    print(f"  {len(stubs)} image(s) awaiting description")
    for path in stubs[:30]:
        print(f"    {path.relative_to(EXTRACTED).as_posix()}")
    if len(stubs) > 30:
        print(f"    ... and {len(stubs) - 30} more")

    print(f"\n  {len(uncurated)} extracted document(s) not cited by any distilled topic")
    for path in uncurated[:30]:
        print(f"    {path.relative_to(EXTRACTED).as_posix()}")
    if len(uncurated) > 30:
        print(f"    ... and {len(uncurated) - 30} more")

    if not stubs and not uncurated:
        print("\n  Nothing outstanding. Every document is extracted and cited by a topic.")
        return 0

    print("\n  Images: open each one and replace the stub with the screen's fields,")
    print("  actions, states and navigation. A screen's structure is the requirement.")
    print("  Documents: distil by TOPIC across sources, not one file per source —")
    print("  mirroring the filing cabinet reproduces the filing cabinet's retrieval problem.")
    return 1

def _plugin_knowledge() -> Path:
    """The knowledge base that ships inside the plugin itself.

    ROOT is the directory the scripts live under: the plugin root when this runs
    from an installed plugin, the checkout root when it runs from source.
    """
    return Path(ROOT) / "knowledge"


def _fallback_to_plugin_if_empty() -> bool:
    """Point reads at the plugin's knowledge base when the current repo has none.

    The knowledge base is installed once per machine, and every repository that has the
    plugin cites that same one — so a developer standing in an application repo can
    query it without that repo carrying a copy that then drifts. A repo that DOES have
    its own distilled knowledge keeps using it: an explicit local corpus always wins.

    Returns True when the fallback was applied, so the caller can say so. Answering from
    a different corpus than the user expected, silently, is the failure worth avoiding.
    """
    if DISTILLED.exists() and any(DISTILLED.glob("*.md")):
        return False
    shared = _plugin_knowledge()
    if not (shared / "distilled").exists():
        return False
    if shared.resolve() == KNOWLEDGE.resolve():
        return False
    _rebind(Path(ROOT))
    return True


def cmd_refresh(args) -> int:
    """Re-extract anything new in inbox/, then rebuild the index. The one-step update.

    Extraction and indexing are separate commands because curation sits between them:
    you extract, a human writes the distilled topics, then you index. `refresh` is for
    the case where that curation has already happened and documents were added since.
    It runs both ends and reports what moved, so nobody has to remember the order or
    notice on their own that an index went stale when a new document landed.
    """
    print("Refreshing the knowledge base")
    print("")
    before = len(list(DISTILLED.glob("*.md"))) if DISTILLED.exists() else 0

    print("[1/2] extract")
    rc = cmd_extract(args)
    if rc not in (0, None):
        print("")
        print("  Extraction reported a problem; the index was NOT rebuilt. Fix the")
        print("  document it names and re-run, so the index never describes a corpus")
        print("  that failed to ingest.")
        return rc

    print("")
    print("[2/2] index")
    rc = cmd_index(args)
    if rc not in (0, None):
        return rc

    after = len(list(DISTILLED.glob("*.md"))) if DISTILLED.exists() else 0
    print("")
    print("  distilled topics: {0} -> {1}".format(before, after))
    if after == before:
        print("  No new topics. If you added documents to inbox/ they are extracted but")
        print("  not yet curated - run `worklist` to see what is waiting for a human.")
    print("")
    print("  This updated the knowledge base in THIS checkout. An installed plugin is")
    print("  cached by version, so the change reaches it only after a version bump and")
    print("  a reinstall:  python scripts/release.py --bump patch")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base ingestion and query")
    parser.add_argument("--workspace", default=None,
                        help="the project whose knowledge base to operate on "
                             "(default: the current directory; read-only commands "
                             "fall back to the plugin's shared corpus when the "
                             "current directory has none)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("extract").set_defaults(func=cmd_extract)
    sub.add_parser("refresh").set_defaults(func=cmd_refresh)
    sub.add_parser("index").set_defaults(func=cmd_index)
    sub.add_parser("topics").set_defaults(func=cmd_topics)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("worklist").set_defaults(func=cmd_worklist)
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)
    p = sub.add_parser("show"); p.add_argument("anchor"); p.set_defaults(func=cmd_show)

    args = parser.parse_args()
    if getattr(args, 'workspace', None):
        _rebind(pathlib.Path(args.workspace).resolve())
    elif args.command in READ_ONLY_COMMANDS and _fallback_to_plugin_if_empty():
        print("(no knowledge base in this repo - reading the plugin's, at "
              + str(KNOWLEDGE) + ")")
        print("")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
