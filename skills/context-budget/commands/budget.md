# Command: budget

Used by the `context-budget` skill.

## Steps
1. Run `python scripts/context-bill.py --budget` and paste the table. Measurement first.
2. Identify the largest reducible items across both ledgers.
3. Give a concrete edit for each — the file, the lines, and what to move where.
4. If a reduction landed, re-run `python scripts/measure-discovery-budget.py`.

## Outputs
- The bill, always-on and per-invocation, labeled as an estimate
- A ranked remediation list with a specific edit per item

## Rules
- An audit that opens with an opinion instead of a number is a review, not an audit.
- Never present the chars-over-four estimate as a measurement.
