#!/usr/bin/env python3
"""
The documentation graph: who cites what across the knowledge base.

  python scripts/doc-graph.py build [--workspace PATH]   # write knowledge/index/doc-graph.json
  python scripts/doc-graph.py summary                    # counts + findings, no write
  python scripts/doc-graph.py mermaid                    # topic-level diagram
  python scripts/doc-graph.py orphans                    # curated but never cited
  python scripts/doc-graph.py dangling                   # cited but does not exist

WHY THIS IS NOT `scripts/graph.py`
-----------------------------------
`graph.py` indexes CODE - paths, exports, classes, functions, imports. It has no concept
of a document, an anchor, or a citation, so it cannot answer the questions that matter
about a corpus whose entire value is provenance.

WHAT THIS ANSWERS THAT A FILE LISTING CANNOT
---------------------------------------------
The corpus is three layers deep:

    context/*.md  --from:-->  distilled/<topic>.md#<anchor>  --source:-->  <original>#page-N

A listing tells you the layers exist. A graph tells you where the chain is BROKEN, and
two breaks matter:

  DANGLING   a `from:` pointing at an anchor no distilled file defines. The claim reads
             as sourced and is not. This is the documentation form of the failure that
             shipped on 2026-09-09, when a summary cited `IClaimLawsWriter.cs` - a file
             whose write had been denied and which therefore never existed. A citation
             that resolves to nothing is worse than no citation, because it survives
             review: the reader sees an anchor and stops checking.

  ORPHANED   a distilled anchor nothing in context/ cites. Not a defect on its own -
             plenty of curated material is reference rather than load-bearing - but a
             large orphan set means curation effort is going somewhere the synthesis
             never reads, which is worth knowing before curating more.

HONEST LIMIT
------------
This is lexical, like `graph.py`. It matches comment shapes with regexes and does not
parse Markdown. It is authoritative about a citation being PRESENT and only suggestive
about one being absent - a provenance comment written in a shape these patterns do not
recognise is invisible here, and shows up as a missing edge rather than as an error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import utc_now  # noqa: E402

# The edge shapes, learned from the corpus rather than assumed. Each was verified against
# the real files before being written here.
ANCHOR_DEF = re.compile(r"\{#([a-z0-9][a-z0-9-]*)\}")
FROM_EDGE = re.compile(r"<!--\s*from:\s*([^#\s]+?)#([a-z0-9][a-z0-9-]*)\s*-->")
SOURCE_EDGE = re.compile(r"<!--\s*source:\s*(.+?)#([^\s>]+)\s*-->")
CROSS_REF = re.compile(r"(\d\d-[a-z0-9-]+\.md)#([a-z0-9][a-z0-9-]*)")
CONFLICT = re.compile(r"⚠️\s*\*\*Conflict\*\*", re.IGNORECASE)


def read(path: Path) -> str:
    """utf-8-sig so a BOM downgrades to a non-event rather than a phantom parse failure."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def build_graph(workspace: Path) -> dict:
    distilled_dir = workspace / "knowledge" / "distilled"
    extracted_dir = workspace / "knowledge" / "extracted"
    context_dir = workspace / "context"

    anchors: dict = {}
    topics: dict = {}
    sources: dict = defaultdict(set)
    edges: list = []

    # ---- layer 2: distilled topics, their anchors, and what they cite -------------
    for path in sorted(distilled_dir.glob("*.md")) if distilled_dir.is_dir() else []:
        text = read(path)
        name = path.name
        found = ANCHOR_DEF.findall(text)
        topics[name] = {
            "file": "knowledge/distilled/" + name,
            "anchors": found,
            "bytes": len(text.encode("utf-8")),
            "conflicts": len(CONFLICT.findall(text)),
        }
        for anchor in found:
            anchors[name + "#" + anchor] = {"topic": name, "anchor": anchor}

        for original, locator in SOURCE_EDGE.findall(text):
            original = original.strip()
            sources[original].add(locator)
            edges.append({"from": name, "to": original, "locator": locator, "kind": "source"})

        for target_file, target_anchor in CROSS_REF.findall(text):
            if target_file == name:
                continue  # a file pointing at its own anchor is navigation, not an edge
            edges.append(
                {"from": name, "to": target_file + "#" + target_anchor, "kind": "cross-ref"}
            )

    # ---- layer 1: the synthesis, and what it claims to be sourced from ------------
    context_files: dict = {}
    for path in sorted(context_dir.glob("*.md")) if context_dir.is_dir() else []:
        # README.md documents the citation FORMAT. Its worked example is a literal
        # `<!-- from: knowledge/distilled/x.md#anchor -->`, which is indistinguishable
        # from a real citation to a lexical matcher and reports as dangling forever.
        if path.name.lower() == "readme.md":
            continue
        text = read(path)
        name = path.name
        refs = [Path(t).name + "#" + a for t, a in FROM_EDGE.findall(text)]
        context_files[name] = {"file": "context/" + name, "cites": len(refs)}
        for ref in refs:
            edges.append({"from": name, "to": ref, "kind": "from"})

    # ---- the findings a listing cannot produce ------------------------------------
    cited = Counter(e["to"] for e in edges if e["kind"] == "from")

    dangling = sorted(
        {ref for ref in cited if ref not in anchors},
        key=lambda r: (-cited[r], r),
    )
    orphans = sorted(a for a in anchors if a not in cited)

    # An extracted document no distilled topic cites: ingested, never curated.
    extracted = set()
    if extracted_dir.is_dir():
        # Paths relative to extracted/, NOT basenames. Six screen folders each hold a
        # screen.md and a code.md, so keying on basename silently collapsed 45 files to
        # 35 and reported the survivors as uncited.
        extracted = {
            p.relative_to(extracted_dir).as_posix() for p in extracted_dir.rglob("*.md")
        }
    uncited_sources = sorted(extracted - set(sources))

    return {
        "version": 1,
        "builtAt": utc_now(),
        "workspace": str(workspace),
        "counts": {
            "contextFiles": len(context_files),
            "topics": len(topics),
            "anchors": len(anchors),
            "sourceDocuments": len(sources),
            "extractedDocuments": len(extracted),
            "edges": len(edges),
            "fromEdges": sum(1 for e in edges if e["kind"] == "from"),
            "sourceEdges": sum(1 for e in edges if e["kind"] == "source"),
            "crossRefs": sum(1 for e in edges if e["kind"] == "cross-ref"),
            "conflicts": sum(t["conflicts"] for t in topics.values()),
        },
        "findings": {
            "dangling": dangling,
            "orphanAnchors": orphans,
            "uncitedExtracted": uncited_sources,
        },
        "mostCited": cited.most_common(12),
        "contextFiles": context_files,
        "topics": topics,
        "sources": {k: sorted(v) for k, v in sorted(sources.items())},
        "edges": edges,
    }


def print_summary(graph: dict) -> None:
    counts = graph["counts"]
    findings = graph["findings"]
    print("Knowledge base document graph")
    print("  context files      {:>5}".format(counts["contextFiles"]))
    print("  distilled topics   {:>5}".format(counts["topics"]))
    print("  anchors            {:>5}".format(counts["anchors"]))
    print("  source documents   {:>5}  (of {} extracted)".format(
        counts["sourceDocuments"], counts["extractedDocuments"]))
    print("  edges              {:>5}  ({} from, {} source, {} cross-ref)".format(
        counts["edges"], counts["fromEdges"], counts["sourceEdges"], counts["crossRefs"]))
    print("  conflicts flagged  {:>5}".format(counts["conflicts"]))

    dangling = findings["dangling"]
    print("\nDANGLING citations ({}) - cited by context/, defined nowhere:".format(len(dangling)))
    if not dangling:
        print("    none - every citation in context/ resolves to a real anchor")
    for ref in dangling[:15]:
        print("    " + ref)

    orphans = findings["orphanAnchors"]
    print("\nORPHAN anchors ({}) - curated, never cited by context/:".format(len(orphans)))
    for ref in orphans[:15]:
        print("    " + ref)
    if len(orphans) > 15:
        print("    ... and {} more  _[trimmed]_".format(len(orphans) - 15))

    uncited = findings["uncitedExtracted"]
    print("\nEXTRACTED but never cited by any distilled topic ({}):".format(len(uncited)))
    for name in uncited[:10]:
        print("    " + name)
    if len(uncited) > 10:
        print("    ... and {} more  _[trimmed]_".format(len(uncited) - 10))

    print("\nMost-cited anchors:")
    for ref, n in graph["mostCited"][:10]:
        print("    {:>3}  {}".format(n, ref))


def _node_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", name.replace(".md", ""))


def print_mermaid(graph: dict) -> None:
    """Topic level only. 258 anchors would render as an unreadable hairball."""
    weight: Counter = Counter()
    for edge in graph["edges"]:
        if edge["kind"] == "from":
            weight[(edge["from"], edge["to"].split("#")[0])] += 1

    print("```mermaid")
    print("graph LR")
    for name in sorted(graph["contextFiles"]):
        print('  C_{}["{}"]'.format(_node_id(name), name))
    for name in sorted(graph["topics"]):
        print('  T_{}("{}")'.format(_node_id(name), name))
    for (src, dst), n in sorted(weight.items(), key=lambda kv: -kv[1]):
        print("  C_{} -->|{}| T_{}".format(_node_id(src), n, _node_id(dst)))
    print("```")


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base document graph")
    parser.add_argument("command",
                        choices=["build", "summary", "mermaid", "orphans", "dangling"])
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    graph = build_graph(workspace)

    if args.command == "build":
        target = workspace / "knowledge" / "index" / "doc-graph.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Written WITHOUT a BOM: every strict reader downstream rejects one.
        target.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Wrote {}".format(target))
        print_summary(graph)
    elif args.command == "summary":
        print_summary(graph)
    elif args.command == "mermaid":
        print_mermaid(graph)
    elif args.command == "orphans":
        for ref in graph["findings"]["orphanAnchors"]:
            print(ref)
    elif args.command == "dangling":
        for ref in graph["findings"]["dangling"]:
            print(ref)
        return 1 if graph["findings"]["dangling"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
