# Command: ground

Used by the `grounding-guard` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Sort every assertion in the draft into verified / inferred / assumed.
3. Apply the four-question gate to every verified claim.
4. Check each named failure mode by name.

## Outputs
- The draft, annotated with confidence markers
- A summary line: verified N, inferred N, assumed N

## Rules
- Downgrading a claim is a success.
- An assumed claim must say what would confirm it. "Unknown" is not a label, it is a shrug.
