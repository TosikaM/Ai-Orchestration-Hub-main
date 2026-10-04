# Command: graph

Used by the `structural-graph` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Run `python scripts/graph.py build` (or `find` / `importers` / `summary` as asked).
3. Report index size and age alongside the answer.

## Outputs
- `~/.orchestrator/cache/<repo-slug>/graph.json`
- The requested query result, with `file:line` for every symbol

## Rules
- Never assert a symbol the index does not contain. Name the ones it does.
- A stale cache is rebuilt, never served.
