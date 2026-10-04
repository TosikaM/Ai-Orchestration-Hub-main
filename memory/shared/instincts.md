# Global Instincts (Promotion Candidates)

<!-- GENERATED from memory/index/entries.json by scripts/memory.py.
     Edit through `python scripts/memory.py`, not by hand: the write path runs
     the redaction and injection guard, and hand edits are lost on the next render. -->

<!-- Everything below the banner is ship-time scaffolding. `scripts/memory.py` rewrites
     this file from the index on the next write, and this orientation prose does not
     survive that render. The durable explanation lives in `memory/README.md`, which is
     hand-maintained and is not rendered from anything. -->

## How this works

An instinct is a trigger-to-action pair: *when you see this, reach for that*. It is the
category the eager-context digest draws from, which makes it the highest-leverage and the
most dangerous of the four — an instinct does not wait to be searched for, it arrives
unasked in the next agent's prompt.

Capture one with:

```
python scripts/memory.py capture --type instinct \
  --title "..." --context "<the trigger>" --resolution "<the action>" [--applies-to <stack>]
```

Two limits worth stating plainly rather than leaving to be discovered.

**The heading is aspirational; the render is not.** The file is named for promotion
candidates, but `scripts/memory.py` renders only entries whose scope is already `shared`.
Candidates that have not promoted yet do not appear here. To see them, and to see exactly
which of the two conditions each one is missing, run
`python scripts/memory.py promote --dry-run`.

**Being in this file is not the same as being injected.** The digest applies its own
floor (`memoryRead.minConfidenceForInjection`) and a hard cap
(`memoryRead.maxInjectedInstincts`) from `config/token-budgets.json`, ranked by
confidence × repo-match. An instinct listed here may sit below the cap and never reach a
prompt; that is the cap working, not a bug. `python scripts/memory.py digest` prints how
many qualifying entries were left out.

Because an instinct fires without being asked for, prefer a narrow trigger to a broad
one. A trigger that matches everything is not an instinct — it is a personality change,
applied to every agent in every repository, and nobody will connect the resulting
behavior back to this file.

<!-- ENTRY FORMAT — rendered, not authored. Each promoted entry appears as:

### <title>
- **Confidence**: <effective, after decay> (recorded <stored value>)
- **Seen in**: <repo>, <repo>
- **Context**: <the trigger — the observable situation>
- **Resolution**: <the action to take when the trigger fires>
- **Applies to**: <domain or stack, or "all">
- **First observed**: <ISO-8601> · **Last reinforced**: <ISO-8601>
- **Counter-examples**: <count, only when one has been recorded>
- **Related**: <title of a weakly-matching entry, when one exists>

Entries are ordered by effective confidence, highest first. The stable `id` and the
`scope`, `seenInRepos`, and `reinforcements` fields live in memory/index/entries.json;
the render surfaces the ones a reader needs and leaves the bookkeeping in the index.
-->

_No entries yet. Memory ships empty — seeding it with invented learnings would poison
the well on day one._
