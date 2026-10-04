# Command: review

Used by the `quality-sentinel` skill.

## Steps
1. Load the parent `SKILL.md` and `contexts/review.md`.
2. Read the whole diff, plus the surrounding context of every changed hunk.
3. Apply the Pre-Report Gate to every candidate finding.
4. Score 0-100 and issue a verdict against the gate threshold.

## Outputs
- Verdict, Score, Blocking, Suggestions, Deliberately skipped

## Rules
- Zero findings is a valid result. Report clean work as clean.
- HIGH and CRITICAL require the snippet, the line, the scenario, and why existing
  guards do not catch it.
- Skip the twelve documented false positives.
