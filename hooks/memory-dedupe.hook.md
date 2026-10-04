---
name: memory-dedupe
trigger: InProcess
matcher: "none"
profiles: [minimal, standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/memory-dedupe.js
description: The memory write guard — redacts, deduplicates, and scores every entry before it can be appended to shared memory. Called at the write site, not fired by an event.
---

# Memory Write Guard

This is the guard that runs before anything is appended to `memory/shared/`. It refuses
writes that carry a secret or an injection marker, decides whether an incoming entry is
new or a restatement of one already stored, and applies the confidence arithmetic that
decides what eventually gets promoted.

Its registry id is `memory:write:redaction`. `scripts/memory.py` is the call site.

## Deliberately not an event hook

Every other guard in this runtime hangs off a Claude Code event. This one is a function,
and the difference is not an implementation detail.

The specification it comes from describes something that "runs before any append to
`memory/shared/*.md`" — a property of the *write path*, not of a moment in a session.
Modeling it as an event would mean the guard runs when the event fires and not otherwise,
which leaves the write path unguarded on every path that does not go through the event.
An unguarded write path is the entire problem. The source material also gave it the
invented trigger `onMemoryWrite`, which corresponds to no real API in any harness, so
there was never a real event to hang it on in the first place.

Not every guard is a hook. Some are just a function you must call, and the honest fix is
to make the call site the only way to write. The handler exports a hook-shaped `run()`
that returns allow, so the runtime can enumerate it uniformly; that entry point is
normally unused, and `guard`, `classify`, and `reinforce` are the real interface.

## Why the redaction half exists

Shared memory syncs to every connected repository, so a captured credential is not a
local mistake — it is an organization-wide replication event.

And stored memory is re-injected into future prompts, which makes the memory store an
*injection* surface as well as a storage surface. A resolution note reading "ignore
previous instructions" becomes a delayed instruction: read back to an agent three months
later, in a different repository, with no human anywhere in the loop.

`guard(entry)` runs `redact.guardFreeText` over the title, context, and resolution. It
throws on a HIGH-tier secret and on any injection marker. There is no flag that turns
that off, and this guard is exempt from the profile system — a profile is a friction
dial, not a security dial, and choosing `minimal` must not quietly disable the guard on
the channel that syncs organization-wide.

## Why the dedupe half is a token control

Shared memory is loaded into the eager context on every invocation, and the digest reader
takes the most relevant entries first. An un-deduplicated file grows without bound, and
its duplicates crowd out distinct lessons — the second copy of a learning displaces a
different learning entirely. Deduplication is a budget mechanism that happens to also
keep the file readable.

`classify` compares the incoming entry against every existing one using a normalized
token-set similarity, and takes the better of the title score and the resolution score.
Comparison is on **title and resolution, never on context**: context is repository-
specific and will differ even when the lesson is word-for-word identical, so including it
guarantees you never detect a duplicate.

At or above 0.72 the action is `reinforce`. Between 0.45 and 0.72 it is
`append-cross-referenced` — a distinct entry that names its neighbour. Below that, a
plain `append`.

## The confidence arithmetic

The promotion rule (confidence ≥ 0.7 **and** seen in ≥ 2 repositories) was a good rule
with no input: nothing in the system ever computed a confidence number, so nothing was
ever promoted. These deltas are that input.

An entry starts at 0.4 — one observation in one repository, deliberately below the floor,
so no single event can promote anything however sure the capturing agent felt. A
reinforcement in a **new** repository adds 0.15 and is the primary path to promotion; in
a repository already seen it adds 0.05. A recorded counter-example subtracts 0.25.
Everything is clamped to [0.1, 0.95].

Decay of 0.05 per ninety days since `lastReinforced` is applied lazily at **read** time
and only for ranking, never as deletion. Deletion-by-decay stays deferred for a stated
reason: calibrating a rate needs real usage data, and guessing one would silently discard
useful learnings. That reasoning holds for deletion and does not hold for ranking — a
lazily applied ranking decay discards nothing, it just stops a three-year-old instinct
from outranking last week's, so a wrong rate there is cheap and correctable.

## Action on a hit

This is not a hook response. `guard` **throws**, and `scripts/memory.py` refuses the
write and reports the field and the reason. `classify` returns an action for the caller
to apply: reinforce the existing entry, append with a cross-reference, or append clean.

## Recovery / escape

**For the redaction guard: none, deliberately.** No environment variable, no profile, no
flag. If a write is refused, the fix is to remove the secret or the injection marker from
the text and write again — which is the outcome you wanted anyway.

**For dedupe:** there is nothing to escape. A `reinforce` verdict is not a rejection; the
lesson is recorded, as a strengthened version of an entry that already exists. If two
genuinely different lessons collide, the narrow fix is to make the title and resolution
say what actually distinguishes them, which is worth doing for the reader regardless.

Thresholds and deltas live in this handler and in `scripts/memory.py`, both governance
files, so changing them requires an override and a logged decision.

## Honest limits

Token-set similarity catches a restatement, not a paraphrase. Two entries expressing the
same lesson in entirely different vocabulary both land, and the file grows. Conversely,
two genuinely distinct lessons about the same subsystem share vocabulary and can cross
the weak threshold on nothing but shared nouns.

The thresholds — 0.72 and 0.45 — are hand-picked and have not been fitted to a corpus.
They are the kind of number that should be revisited once there is real data, and this
document is not going to pretend they were derived.

The confidence arithmetic counts repetition, not truth. A wrong lesson observed in two
repositories promotes exactly as readily as a right one; nothing here evaluates whether
an entry is correct, and the counter-example delta only applies if a human records one.

The redaction guard catches what `config/redaction-patterns.json` describes at HIGH tier.
A credential shaped like nothing in that file passes, and the guard reports clean.

And this only guards writes that go through the call site. A file appended to
`memory/shared/` by hand, by an editor, or by any code that does not call `guard` is
unguarded — which is the whole reason the design insists the call site be the only way
in, and the reason that insistence has to be maintained rather than assumed.
