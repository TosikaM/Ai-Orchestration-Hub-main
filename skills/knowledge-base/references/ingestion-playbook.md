# Reference: The Knowledge Ingestion Playbook

> **Progressive disclosure.** Load this when actually ingesting, not when querying.

## The Shape Of The Problem

Client documentation arrives as a pile: PDFs, Word documents, exported wikis, email
threads saved as attachments, a spreadsheet of requirements, three versions of the same
contract with no indication which is current.

The naive move is to dump it all into context and let the model sort it out. That fails
in three specific ways, and each one is worth naming because each has a different fix:

1. **It blows the budget.** A 40-page specification is roughly 25,000 tokens. Five of
   them is most of a window, spent before anybody asks a question.
2. **It cannot be cited.** "The spec says X" with no anchor is exactly the failure mode
   the grounding contract exists to prevent, imported wholesale from a different domain.
3. **Contradictions vanish.** Two documents disagreeing about a retention period is the
   single most valuable thing in the corpus, and flattening them into one context window
   makes the model silently pick one.

## The Four Stages

### 1. Inbox — never edited

`knowledge/inbox/` holds source documents exactly as received, original filenames intact.
This directory is append-only in practice. If a client sends a revision, it lands beside
the original with its own name; it does not replace it. Version history is content.

### 2. Extract — mechanical, reproducible

```
python scripts/ingest-knowledge.py extract
```

One `.md` per source in `knowledge/extracted/`, with page or section markers preserved
as `<!-- page: 14 -->`. Those markers are what make a citation resolvable back to the
original, so extraction that drops them has failed even if the text is perfect.

**If extraction is wrong, fix the extractor and re-run.** Never hand-patch the output.
A hand-patched extraction no longer corresponds to its source, and once that is true of
one file nobody can trust the citation on any of them.

### 3. Distil — the part that needs judgment

This is not summarization. It is reorganization **by topic**, across documents.

| Wrong | Right |
|---|---|
| `distilled/MSA-2026.md` | `distilled/data-retention.md` citing MSA §7, SOW-2 §3, and the security addendum |
| One file per source | One file per question somebody will actually ask |

Organizing the knowledge base to mirror the filing cabinet reproduces the filing
cabinet's retrieval problem, which is the problem you were trying to solve.

Every distilled paragraph carries provenance:

```markdown
## Retention Period {#retention-period}

Customer transaction records are retained for 7 years from the transaction date.
<!-- source: MSA-2026.pdf p.14 §7.2 -->

Log data is retained for 90 days.
<!-- source: security-addendum-v3.pdf p.4 -->

> ⚠️ **Conflict.** `SOW-2.pdf` p.9 states 5 years for transaction records. MSA-2026 is
> dated 2026-03-11 and SOW-2 is dated 2025-11-02, so MSA is more recent — but the SOW
> may govern its own scope of work specifically. **Unresolved. Ask the client.**
```

That conflict block is the highest-value output of the whole pipeline. Do not resolve it
silently by preferring the newer document.

### 4. Index

```
python scripts/ingest-knowledge.py index
```

Builds `knowledge/index/knowledge-index.json`: topic, anchor, source list, keywords,
byte size. Only this index and the topic headings are ever eagerly loaded, capped by
`knowledgeDigest` in `config/token-budgets.json`.

## Redaction Runs On The Way In

Client documents carry names, email addresses, contract values, internal hostnames, and
occasionally credentials in an appendix nobody remembered was there. Ingestion runs the
redaction scan and **refuses on a HIGH-tier finding**. MEDIUM findings are reported and
auto-redactable ones are replaced with their token.

Do not work around this by editing files under `extracted/` — see stage 2.

## Quality Bar For A Distilled Document

Before it ships:

- [ ] Every factual paragraph has a `<!-- source: -->` comment
- [ ] Every heading has a stable `{#anchor}` — anchors are cited and must not churn
- [ ] Conflicts are marked, dated, and left unresolved where they genuinely are
- [ ] Nothing has been added that is not in a source. **The distiller does not know
      things.** If the corpus does not say it, the distilled document does not say it.
- [ ] The document answers a question somebody would ask, not a document somebody sent
