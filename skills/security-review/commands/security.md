# Command: security

Used by the `security-review` skill.

## Steps
1. Load the parent `SKILL.md`. Scope to the diff unless told otherwise.
2. Run the eight passes.
3. For each candidate, establish the exploit path before writing it down.
4. Run `python scripts/audit-agent-surface.py` for pass 8.

## Outputs
- Findings table: severity, file:line, attack scenario, fix
- A verdict, including a clean one

## Rules
- Severity without a concrete scenario is a suggestion. File it as one.
- A clean diff is reported as clean.
