# Command: analyze

Used by the `repo-context-builder` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Run all five Mandatory Steps in order. Do not summarize the protocol — run it.
3. Emit the context file and the trace map.

## Outputs
- `.github/orchestrator-context.md`, created or updated
- A trace map for the analyzed feature, every layer cited
- For a multi-repo trace: `field-trace-index.md`

## Rules
- Step 3 traces EVERY layer. Tracing one and inferring the rest is the usual failure.
- Never overwrite `## Integration Points` or `## Verified Commands`.
- A layer you expected and did not find is the most valuable line in the analysis. Say so.
