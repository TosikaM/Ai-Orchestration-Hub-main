# Project context — CNP Platform Modernization — Phase 1

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

Generated 2026-09-09T13:11:25Z.
