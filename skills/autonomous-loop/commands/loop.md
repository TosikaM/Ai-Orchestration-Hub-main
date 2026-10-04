# Command: loop

Used by the `autonomous-loop` skill.

## Steps
1. Load the parent `SKILL.md`.
2. State the goal and the stop condition in one line each, before iteration 1.
3. Iterate. Report what changed, what the check said, what is next, every time.
4. Halt on any kernel limit and escalate with a concrete question.

## Outputs
- A per-iteration log
- The final state and the specific blocker, if any

## Rules
- Two iterations with no state change is a stall. Stop; do not spend the rest of the budget.
- Runs over five minutes go through `scripts/detach.ps1` and break on the EXIT sentinel.
