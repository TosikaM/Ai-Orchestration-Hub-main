# Knowledge Base

This is where client and project documentation becomes something an agent can **cite**.

If you are about to drop a folder of PDFs in here, read the four short paragraphs under
"Adding Documents" and nothing else. The rest of this file explains the rules those four
steps are enforcing, and `skills/knowledge-base/references/ingestion-playbook.md` covers
the part that needs judgment — curation — in detail.

## Why Not Just Paste the Documents Into Context

The obvious approach is to load the documents into the model's context and let it sort
them out. It fails three ways, and each one needs a different fix, which is why the
pipeline has stages rather than a single step.

**It blows the budget.** A 40-page specification is roughly 25,000 tokens on the four-
characters-per-token planning ratio this repository uses. Five of them is most of a
window, spent before anybody has asked a question.

**It cannot be cited.** "The spec says X" with no anchor is exactly the failure the
grounding contract exists to prevent, imported wholesale from a different domain. An
answer you cannot trace is an answer you cannot check, and one that is wrong looks
identical to one that is right.

**Contradictions vanish.** Two documents disagreeing about a retention period is the most
valuable single thing in the corpus. Flattened into one context window, the model picks
one, says nothing, and the disagreement — the thing somebody needed to know about — is
gone.

## The Four Stages

```
knowledge/inbox/       source documents, exactly as received      never edited
knowledge/extracted/   mechanical extraction, markers preserved   never hand-patched
knowledge/distilled/   curated BY TOPIC, provenance on every claim
knowledge/index/       the retrieval index                        generated
```

**`inbox/` is never edited.** It holds the documents as they arrived, original filenames
intact. If a client sends a revision it lands beside the original under its own name; it
does not replace it. Which version said what, and when, is content.

**`extracted/` is never hand-patched.** Extraction is mechanical and reproducible, with
page markers preserved as `<!-- page: 14 -->` because those markers are what make a
citation resolvable back to the original. If the extraction is wrong, fix the extractor
and re-run. A hand-patched extraction no longer corresponds to its source, and once that
is true of one file, no citation anywhere in the corpus can be trusted — you would have to
check them all by hand to know which ones still hold.

**`distilled/` is curated by topic, not by document.** This is the stage that needs a
person. One file per question somebody will actually ask — `data-retention.md` citing the
MSA, the SOW and the security addendum — not one file per document you were sent.
Organizing the knowledge base to mirror the filing cabinet reproduces the filing cabinet's
retrieval problem, which is the problem you were solving. Every factual paragraph carries a
`<!-- source: -->` comment, and every heading carries a stable `{#anchor}`, because the
anchor is what a citation points at.

**`index/` is generated.** `knowledge/index/knowledge-index.json` holds topic, anchor,
source list, keywords and byte size. Rebuild it; never edit it.

## Adding Documents

1. Drop the files in `knowledge/inbox/`. Any structure you like; subdirectories are
   preserved through extraction.
2. Run `python scripts/ingest-knowledge.py extract`. This writes one `.md` per source into
   `knowledge/extracted/` and prints what it did, what it refused, and what it could not
   handle.
3. Curate the extracted text into `knowledge/distilled/`, by topic, with provenance on
   every claim. This is the step that cannot be automated; the playbook has the quality
   bar and a worked example.
4. Run `python scripts/ingest-knowledge.py index`.

Then `python scripts/ingest-knowledge.py status` tells you where the corpus stands, and
`search`, `topics` and `show` query it.

Extraction alone is not a knowledge base. If `status` reports documents extracted and
nothing distilled, what you have is raw material — searchable by nobody, citable by
nothing.

## File Types and Optional Dependencies

Markdown, plain text, CSV, JSON, YAML and reStructuredText are read directly. Two formats
need a dependency that is deliberately not required to install this repository:

```
pip install pypdf         # PDFs
pip install python-docx   # Word .docx
```

An absent dependency is **reported**, never worked around: the file is listed as not
extracted, with the install command, rather than skipped in a way you would have to notice.

A scanned PDF is the case worth knowing about. When every page comes back with no text
layer, the document is a picture of text and needs OCR, which is not a dependency this
repository takes. It is reported as needing manual handling and is **not ingested**.
Writing an empty document that looks successfully processed is the failure mode this
avoids — it would sit in the corpus, be indexed, return no matches for anything, and give
no indication that the reason is an extraction problem rather than the document simply not
covering the subject.

## Redaction Runs on the Way In

Client documents carry names, email addresses, contract values, internal hostnames, and
occasionally a credential in an appendix nobody remembered was there. Extraction runs the
redaction scan from `config/redaction-patterns.json` against every document and:

- **refuses on a HIGH-tier finding** — the document is not written to `extracted/`, and the
  finding IDs are printed. Remove the credential from the source, or handle that document
  outside the corpus.
- auto-redacts MEDIUM-tier findings that are marked auto-redactable, replacing each with
  its token, and reports the count per document.

Refusing rather than sanitizing is deliberate for the HIGH tier: a silently redacted
document reads as complete, so nobody goes back to deal with the credential that is still
sitting in the source file. Working around the refusal by editing something under
`extracted/` breaks stage 2 and takes the whole corpus's citations with it.

## Contradictions Are Content

When two sources disagree, **record the disagreement with dates**. Do not resolve it by
preferring the newer document.

```markdown
> ⚠️ **Conflict.** `SOW-2.pdf` p.9 states 5 years for transaction records. MSA-2026 is
> dated 2026-03-11 and SOW-2 is dated 2025-11-02, so MSA is more recent — but the SOW may
> govern its own scope of work specifically. **Unresolved. Ask the client.**
```

The indexer detects these blocks and counts them, and `index` prints every one it found.
The reason for the ceremony is that "newer wins" is a rule that is right most of the time
and catastrophic the rest of it: a scope-specific SOW routinely overrides a general master
agreement regardless of date, and a distiller who silently applies recency has produced a
knowledge base that is confidently wrong on exactly the questions somebody escalated.

A recorded conflict is the highest-value output of this pipeline. It is the thing nobody
knew and somebody needed to ask.

## The Budget Note

Only the topic index loads eagerly, capped by `eager.layers.knowledgeDigest` in
`config/token-budgets.json`. Distilled bodies are read on demand, by anchor, when a query
actually needs them.

That is the whole reason the pipeline is shaped this way. The corpus can grow without the
per-session cost growing with it, because what is always in context is a list of topics and
citations, not the documents. `index` prints the digest size against the cap and tells you
when the topic list has outgrown it — the fix at that point is usually to consolidate
topics, not to raise the ceiling.

## When the Corpus Does Not Cover It

`search` says so, explicitly, and that is a real answer rather than a failure. **An honest
"not found" outranks a plausible guess.** The failure this prevents is an agent treating an
empty result as permission to answer from general knowledge and presenting it with the
authority of a cited corpus — which is indistinguishable, to the reader, from a real
citation.
