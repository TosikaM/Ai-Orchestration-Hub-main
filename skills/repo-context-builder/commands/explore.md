# Command: explore

Used by the `repo-context-builder` skill. Read-only fast path.

## Steps
1. Load the parent `SKILL.md`.
2. Run Mandatory Steps 1, 2, and 5 only — structure, conventions, dependencies.
3. Tag every finding with a confidence marker.
4. State explicitly what was NOT examined.

## Outputs
- A findings summary, confidence-tagged
- An explicit "not examined" list

## Rules
- This command does not write the context file. `/analyze` does that.
- The "not examined" list is mandatory output, not a footnote. An exploration that
  implies completeness is worse than one that admits its scope.
