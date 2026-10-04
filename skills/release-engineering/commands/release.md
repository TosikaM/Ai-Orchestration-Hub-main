# Command: release

Used by the `release-engineering` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Run the readiness gate. Report every blocker without softening it.
3. Read the current version from the manifest. Propose the bump with a justification.
4. Write release notes, the CHANGELOG entry, and the rollback note.

## Outputs
- GO or BLOCKED, with reasons
- Release notes, CHANGELOG entry, rollback note

## Rules
- Release notes describe what a user can now do that they could not before.
- Never recall a version number. Read it.
