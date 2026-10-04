# Command: sdlc-start

Used by the `sdlc-orchestrator` skill.

## Steps
1. Load the parent `SKILL.md` and run the mandatory context load.
2. Enter the DAG at `entry` from `config/pipeline-graph.json` — phase 0, CLASSIFY & PLAN.
3. Run every phase in order. `review` and `test` are siblings and run in parallel.
4. Stop at each human-gated phase, write the gate artifact, and wait for a verdict.
5. On `complete`, capture learnings and summarize.

## Outputs
- `memory/sessions/<pipelineId>.checkpoint.json` — resumable state, written at every gate
- A gate artifact per human-gated phase
- The change itself, verified

## Rules
- Never restart a pipeline that has a checkpoint. Resume at the recorded phase.
- Never clear your own human gate.
- A phase whose tooling is absent is dropped and reported as dropped, never faked.
