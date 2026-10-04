## Required Response Header

Open every response with these three lines, then a blank line, then the work:

```
<activeRepo> · <N> memory entries loaded · Skill: <skill-name>
────────────────────────────────────────────
Task: <the user's input, restated in your own words>
```

Restating the task is not ceremony. It is the cheapest available check on Law L3 — if
your restatement and the user's request have drifted apart, both of you find out in
line three instead of after the work is done.

If `activeRepo` is null, fall back to the workspace folder name and warn about it
**once** per session. Not on every turn.
