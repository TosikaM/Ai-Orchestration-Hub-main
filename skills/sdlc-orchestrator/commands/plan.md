# Command: plan

Used by the `sdlc-orchestrator` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Run phases 0 through 2 only — classify, stories, impact analysis.
3. Stop at the impact gate. Do not implement.
4. List the risks and the unknowns explicitly, each with what would resolve it.

## Outputs
- The plan, phase by phase, with the files each phase will touch
- A risks table: risk, likelihood, what would de-risk it
- An unknowns list, each with the cheapest probe that would settle it

## Rules
- An unknown you could have resolved with one read is not an unknown. Read it.
- Estimate in blast radius (files, layers, repos), not in hours.
