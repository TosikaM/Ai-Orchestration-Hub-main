## Token Discipline

Read narrowly before you read widely. Grep to locate, then read the range — opening a
whole file to find one function is the most common avoidable cost in this system.

- Prefer the structural graph (`python scripts/graph.py`) over re-exploring the tree.
  It exists so you spend roughly two thousand tokens on a symbol summary instead of
  re-reading source you already indexed.
- Reference material in a skill's `references/` folder loads **on demand only**. Do not
  pull one in unless the task needs it.
- When you trim or truncate anything, say so with an explicit marker. Continuing past a
  cut as though you had read the remainder is a named failure mode, not an accident.

The reason for the discipline: discovery-tier cost is paid by every user, in every
repo, on every conversation, before anyone types anything. A kilobyte saved there is
worth far more than a kilobyte saved in a response nobody re-reads.
