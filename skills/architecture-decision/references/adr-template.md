# ADR-{{NUMBER}}: {{TITLE}}

- **Status:** Proposed | Accepted | Superseded by ADR-NNNN
- **Date:** {{YYYY-MM-DD}}
- **Deciders:** {{NAMES}}
- **Decision log id:** {{d-xxxx}}

## Context

What forces are in play? Cite the constraints — a `file:line`, a measurement, a stated
requirement. A tradeoff argued against imagined constraints is fiction, and fiction
formatted as an ADR outlives the person who wrote it.

## Decision

The option chosen, in one sentence, in the active voice.

## Options considered

### Option A — {{NAME}} (chosen)

- **How it works:**
- **What it costs:**
- **What it forecloses:**

### Option B — {{NAME}} (rejected)

- **How it works:**
- **What it costs:**
- **Why rejected:**

## Strongest argument against this decision

The best case the other side has, written as well as they would write it. If you cannot
write a good one, you have not understood the tradeoff yet — go back to Options.

## Consequences

- **Positive:**
- **Negative:**
- **Reversal cost:** what it takes to undo this in six months, in hours and in blast radius

## Follow-ups

Work this decision creates, with owners.

---

<!--
Two rules that make the difference between an ADR and a press release:

1. The rejected alternatives and the reasons are the part a future reader actually
   needs — usually because they are about to propose one of them again.

2. This file must be joined to the decision log, or nobody will ever find it:

     python scripts/decision.py log \
       --decision "<the one-sentence decision>" \
       --rationale "<why>" \
       --alternatives "<what was rejected and why>" \
       --adr docs/adr/NNNN-slug.md

   An ADR that is not in the log is never surfaced to the agent who needs it in four
   months. An unread ADR is a diary entry.
-->
