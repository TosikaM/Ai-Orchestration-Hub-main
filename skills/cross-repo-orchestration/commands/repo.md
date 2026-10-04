# Command: repo

Used by the `cross-repo-orchestration` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Dispatch on the sub-command: `status`, `list`, `switch <name>`, `connect <path>`,
   `group <name>`, `band show|advance`.
3. Report the resulting state.

## Outputs
- The updated `~/.orchestrator/state/connected-repos.json`
- For `band advance`: the updated band file with the new shared contracts

## Rules
- Execution order is dependency-first: producers before consumers.
- Upstream contracts are consumed as named. Renaming downstream breaks the band silently.
