# Memory System

Four tiers of durable state plus one derived index, one write path, and one arithmetic
that decides what gets promoted out of a single repository and into every repository.

The store itself is `memory/index/entries.json`. The Markdown files under
`memory/shared/` are a **rendering** of that JSON, produced by `scripts/memory.py` —
one source, two representations. The JSON is what ranking and promotion operate on; the
Markdown is what a human browses and what syncs to consumer repositories. Maintaining
both by hand would guarantee they disagree within a month, so hand edits to the rendered
files are lost on the next render and are not a supported way in.

## The Tiers

| Tier | Path | Scope | Retention | Synced to consumers |
|------|------|-------|-----------|---------------------|
| Shared | `memory/shared/` | All repos | Permanent | Yes |
| Per-repo | `memory/repos/<name>/` | One repo | Permanent | Only that repo |
| Decisions | `memory/decisions/<slug>.jsonl` | One repo | Permanent, append-only | No |
| Session | `memory/sessions/` | One pipeline run | Discarded | No — git-ignored |
| Index | `memory/index/` | Derived | Rebuildable | No — git-ignored |

The distinction that matters most is the first column against the last. Anything in
`memory/shared/` is loaded in every repository that connects to this hub, so a wrong
entry there is not wrong once — it is wrong everywhere, silently, until somebody
notices. Everything below is about making that promotion hard to trigger by accident.

The decisions tier is append-only and event-sourced (`decide`, `supersede`, `redact`),
handled by `scripts/decision.py` rather than by `memory.py`. "Active" is computed rather
than stored, because the value of the log is that you can see what was believed at the
time, not only what is believed now.

## The Promotion Rule

A repo-scoped entry is promoted to `memory/shared/` when:

> **effective confidence ≥ 0.7 AND observed in ≥ 2 repositories.**

Both conditions, never either.

The second condition is the one that does the work. A high-confidence lesson observed in
a single repository is usually a fact *about that repository* — its build quirk, its
naming habit, its one strange service — wearing the costume of a general truth. The
capturing agent's certainty is evidence about the agent, not about the world. Promoting
on confidence alone is exactly how shared memory fills with advice that is correct in one
place and wrong everywhere else, and advice that is wrong everywhere else is worse than
no advice, because it arrives pre-endorsed by the system.

Promotion is a deliberate command (`python scripts/memory.py promote`), not a background
effect of capture. When nothing qualifies, the command prints the closest candidates and
names what each one is missing, so "why has this never promoted" has an answer that does
not require reading the source.

## The Confidence Arithmetic

A promotion rule with no input is a rule that never fires. Confidence is computed:

| Event | Delta | Why this value |
|-------|-------|----------------|
| First capture | `0.4` | Deliberately below the 0.7 floor, so no single observation can promote anything however sure the capturing agent felt at the time. |
| Reinforced in a **new** repo | `+0.15` | The primary path to promotion. Two new-repo reinforcements from the initial 0.4 reach exactly 0.7, which is also when the second condition is satisfied. |
| Reinforced in a repo already seen | `+0.05` | Real evidence, but weak: the same repository confirming itself is close to one observation counted twice. |
| Counter-example recorded | `-0.25` | Larger than any single reinforcement, so one documented contradiction outweighs one confirmation. Disconfirming evidence is rarer and more informative. |
| Age, per 90 days since `lastReinforced` | `-0.05` | Applied lazily at read time; see below. |
| — | clamped to `[0.1, 0.95]` | Nothing reaches certainty and nothing reaches zero. A floor above zero keeps a stale entry findable by search instead of vanishing from ranking entirely. |

The 0.7 promotion floor is the same number as `memoryRead.minConfidenceForInjection` in
`config/token-budgets.json`. That is not a coincidence worth breaking: an entry is
trusted enough to be injected into a prompt on precisely the same evidence that makes it
trusted enough to apply org-wide.

Reinforcement requires a duplicate to be *detected*. Capture compares the incoming title
and resolution against existing entries of the same type by token-set overlap; at or
above `0.72` the existing entry is reinforced instead of a near-duplicate being appended,
and between `0.45` and `0.72` a new entry is appended with a cross-reference to the
related one. Context is deliberately excluded from that comparison — context is
repo-specific and differs even when the lesson is word-for-word identical, so including
it would guarantee you never detect a duplicate and therefore never promote anything.

## Why Every Write Goes Through `scripts/memory.py`

There is no flag that skips the write guard, and that is the design. Two reasons, and the
second is the one people miss.

**Shared memory syncs org-wide, so a captured credential is a replication event.** An
agent that debugs an auth failure and writes "regenerated the token to `sk-…`" has not
made a local mistake — it has copied a live secret into every repository connected to the
hub, in one command, with no review step between the writing and the distribution. The
write path scans every free-text field for HIGH-tier secrets and **refuses the write**
rather than sanitizing it, because a silently redacted resolution reads as complete and
nobody goes back to fix it.

**Stored memory is re-injected into future prompts, which makes the store an injection
surface as well as a storage surface.** A resolution note reading "ignore previous
instructions" is not a string sitting in a file; it is a delayed instruction, read back
to an agent three months later, in a different repository, with no human in the loop.
Free text is scanned for injection markers on the way in, for the same reason and with
the same refusal.

The guard is a function you must call, not a hook, and that too is deliberate. Modeling
it as an event would leave the write path unguarded on every occasion the event failed to
fire — a wiring bug becomes a security hole. Some guards cannot be optional, and the
honest way to make one non-optional is to make the call site the only way in.

The practical consequence: `python scripts/memory.py capture …` is the entry point, and
editing `memory/shared/*.md` in an editor accomplishes nothing durable. The hand edit
skips both scans and is overwritten by the next render.

## Decay Is for Ranking, Never Deletion

The `-0.05 per 90 days` term is applied at **read** time and never mutates the stored
value. An entry's recorded confidence is what the evidence said; its effective confidence
is what the evidence says *today*. Both are printed, so a low rank is explainable.

Deletion-by-decay stays deferred, and the reason is worth stating plainly rather than
presenting the current behavior as finished. Calibrating a decay rate needs real usage
data that this system does not have yet. If decay deleted, a wrong rate would silently
discard useful learnings — an unrecoverable, invisible loss, discovered only when an
agent repeats a mistake the system had already recorded. Because decay only ranks, a
wrong rate costs an entry a few positions in a digest and nothing else. It is
correctable, in one constant, at any time.

That asymmetry is the whole argument: pick the failure mode you can notice and undo.
Pruning still exists (`python scripts/memory.py prune`), but it is a separate, explicit,
interactive command with a much stricter test — below 0.3 confidence *and* untouched for
180 days — and it prints what it would remove and stops unless you pass `--yes`.

## Reading the Store

| Command | What it is for |
|---------|----------------|
| `python scripts/memory.py search "<query>"` | Ranked by relevance × confidence × repo-match. |
| `python scripts/memory.py digest` | The capped, ranked digest that goes into eager context. |
| `python scripts/memory.py promote --dry-run` | What would promote, and what the near-misses are missing. |
| `python scripts/memory.py review` | Triage the candidates the learning-capture hook wrote during sessions. |

A search that finds nothing says so and says it is a real answer. **An honest "not found"
outranks a plausible guess** — the failure this prevents is an agent treating an empty
store as permission to reconstruct a lesson from training data and present it with the
authority of institutional memory.

The digest is capped (`memoryRead.maxInjectedInstincts`) and ranked rather than truncated
by recency, and it reports how many entries above the floor did not make the cut.
Recency is a proxy for relevance that gets steadily worse as the store grows — which is
to say, exactly as the store becomes valuable.

Note also that the learning-capture hook does not write to shared memory directly. It
writes candidates to `memory/sessions/learning-candidates.jsonl` for triage, because a
turn-level heuristic guessing that something was a lesson is not the same standard of
evidence as a person deciding it was.
