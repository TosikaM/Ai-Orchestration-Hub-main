# Command: implement

Used by the `cqrs-developer` skill.

## Steps
1. Load the parent `SKILL.md` and `.github/orchestrator-context.md`.
2. Establish blast radius before the first edit: importers, affected exports.
3. Identify the mapping mechanism for every layer the change crosses.
4. Implement in dependency order.
5. Run `verification-loop` and report the actual output.

## Outputs
- The code, with every file path named
- The verification result, verbatim
- What you deliberately did not do

## Rules
- No refactoring you were not asked for. No speculative abstraction.
- Never edit a check to make it pass.
