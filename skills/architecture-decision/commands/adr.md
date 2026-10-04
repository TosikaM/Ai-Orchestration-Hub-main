# Command: adr

Used by the `architecture-decision` skill.

## Steps
1. Load the parent `SKILL.md` and `references/adr-template.md`.
2. Confirm the decision has a real fork. If not, say so and stop.
3. Recover and cite the constraints. Frame two or more options.
4. Recommend one and write the strongest argument against it.
5. Write `docs/adr/NNNN-<slug>.md`, then log the decision event.

## Outputs
- The ADR file
- A decide event in `memory/decisions/<repo-slug>.jsonl` carrying the ADR path

## Rules
- An ADR without the rejected alternatives is a press release.
- Step 5 is not optional. An unlogged ADR is never surfaced again.
