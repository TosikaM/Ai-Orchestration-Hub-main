# Command: learn

Used by the `continuous-learning` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Classify: anti-pattern, best practice, tool chain, or instinct.
3. Deduplicate against existing entries on title and resolution — never on context.
4. On a strong match, reinforce the existing entry instead of appending.
5. Write through `python scripts/memory.py capture`. That is the only supported path.

## Outputs
- A new or reinforced entry, with its confidence value
- Whether it now meets the promotion rule

## Rules
- The write path runs redaction and injection scanning. There is no skip flag.
- Nothing is promoted on a single observation, whatever the confidence felt like.
