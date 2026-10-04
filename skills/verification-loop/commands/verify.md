# Command: verify

Used by the `verification-loop` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Resolve commands from `config/stack-mappings.json` for the detected stack.
3. Run all six phases in order.
4. Report each as pass / fail / not run, with the actual output.

## Outputs
- The six-phase table
- The actual command output for every failure

## Rules
- "Not run" is never reported as "passed".
- On a total command miss, ask once and persist the answer under `## Verified Commands`.
