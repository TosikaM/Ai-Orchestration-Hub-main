# Command: pipeline

Used by the `sdlc-orchestrator` skill.

## Steps
1. Read `memory/sessions/*.checkpoint.json` for this workspace.
2. Report every pipeline: id, current phase, phase statuses, scores, pending gates.
3. With an argument (`resume`, `abandon`, `approve`), act on the named pipeline.

## Outputs
- The pipeline state table
- For `resume`: re-entry at the recorded phase

## Rules
- Report a stalled pipeline as stalled. A pipeline waiting on a gate nobody knows about
  is the most common way work quietly stops.
