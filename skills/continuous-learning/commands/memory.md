# Command: memory

Used by the `continuous-learning` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Dispatch: `search <query>`, `promote`, `prune`, or a bare invocation for a summary.
3. Rank results by confidence, recency, and repo match — never by recency alone.

## Outputs
- Ranked matches, each with confidence, repos seen, and last reinforced
- For `promote`: what crossed the threshold and why

## Rules
- Recency degrades as a relevance proxy exactly as the store becomes valuable.
- `prune` is interactive by default and never silent.
