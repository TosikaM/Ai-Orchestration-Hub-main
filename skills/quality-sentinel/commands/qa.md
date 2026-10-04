# Command: qa

Used by the `quality-sentinel` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Generate end-to-end specs for the user-visible paths the change affects.
3. Generate manual test cases for what automation cannot reach.
4. If a browser connector is unavailable, emit the specs and say they were not run.

## Outputs
- E2E spec files
- A manual test case table: id, steps, expected, actual

## Rules
- Never describe the result of a test run that did not happen.
- A manual case with no expected result is a note, not a test case.
