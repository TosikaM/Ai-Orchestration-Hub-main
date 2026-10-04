# Command: knowledge

Used by the `knowledge-base` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Dispatch: `ingest`, `search <query>`, `topics`, `show <anchor>`.
3. Answer with the citation inline — distilled anchor plus the original source and page.

## Outputs
- For a query: the answer with citations, ranked
- For ingest: the extraction and index report, plus any redaction findings

## Rules
- If the corpus does not cover it, say so. That is the answer this skill makes possible.
- Never blend general knowledge into a cited answer without labeling it.
