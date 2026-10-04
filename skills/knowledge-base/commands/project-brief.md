# Command: project-brief

Used by the `knowledge-base` skill. Synthesises `context/` from `knowledge/distilled/`.

## Steps
1. Load the parent `SKILL.md`.
2. `python scripts/ingest-knowledge.py worklist` — refuse to synthesise while images are
   undescribed or documents uncurated. A brief built on a corpus that is half stubs is a
   brief that silently omits whatever those stubs contained.
3. `python scripts/project-context.py scaffold` if `context/` does not exist.
4. Delegate, one agent per concern, because these are genuinely different readings:
   - **ba** -> `00-overview.md`, `02-features.md` — what is being built and for whom
   - **analyst** -> `01-domain-model.md`, `05-integrations.md` — entities and boundaries
   - **architect** -> `04-business-rules.md`, `07-decisions.md` — rules and tradeoffs
   - **qa** -> `03-screens.md` — screens, and especially the states nobody drew
5. Every agent writes `06-open-questions.md` as it goes. It is an output, not a leftover.
6. `python scripts/project-context.py check` must pass.

## Outputs
- A populated `context/`, every claim carrying `<!-- from: knowledge/distilled/... -->`
- Open questions split into blocking, non-blocking with a stated assumption, and
  contradictions between sources

## Rules
- **Synthesise from `distilled/`, never from `inbox/` or `extracted/`.** Distillation is
  where contradictions get caught; skipping it means silently picking one source.
- **A claim with no source is an assumption.** It goes in open questions with the
  assumption written down, not in the brief where the next reader takes it for a fact.
- **Never resolve a contradiction silently.** Record both with dates.
- Zero open questions after a first handover means the documents were paraphrased.
