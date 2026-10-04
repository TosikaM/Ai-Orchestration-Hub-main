---
name: citation-guard
trigger: Stop
matcher: ".*"
profiles: [standard, strict]
mode: sync
blocking: false
handler: hooks/runtime/handlers/citation-guard.js
description: Audits the turn's final response for claims about this codebase that shipped without a verifiable file:line, and appends the gaps as a warning.
---

# Citation Guard

At `Stop`, this reads the assistant's last message out of the transcript and looks for
sentences that assert something about *this* codebase without a `file:line` anywhere on
the line. Gaps are appended to the turn as a warning. It runs inside
`stop:dispatcher:sync` alongside the human gate, so the whole synchronous Stop phase
costs one Node startup rather than one per hook.

It replaces a hook the source material specified with `trigger: onChatResponse`, which
corresponds to no real API. `Stop` is the real event and is a better fit besides: it
fires once when the turn is finished, over the complete response, rather than partway
through a stream.

## Why this exists

The characteristic failure of an agent working in an unfamiliar repository is not the
confident wrong answer that reviews catch. It is the plausible sentence that nobody
challenges — "the auth middleware validates the token before dispatch" — which is true of
most codebases with auth middleware and may be false of this one. It reads as reporting.
It is actually recall from training, dressed as observation.

Negative claims are the worst of the class and get the least scrutiny. "There is no
handler for that" ends an investigation, produces no artifact anyone can review, and is
believed precisely because it sounds like something you could only know by looking.

## Deliberately advisory, and this is the design

This hook does not block, and it stays non-blocking even though the runtime is fully
capable of blocking a `Stop` — the human gate in the same dispatcher does exactly that.

The reason is worth stating rather than hiding. The detector is lexical. A lexical
detector applied to prose has a false-positive rate that would make blocking intolerable,
and a gate that fires wrongly one time in five gets disabled inside a week — after which
you have neither the gate nor the warning. Advisory-and-installed beats
blocking-and-removed.

What does block is the fact-forcing gate, one layer earlier, on the action rather than
the sentence. That is the right division of labor: police actions strictly, police prose
visibly. Making both strict would break the tool. Making both advisory would reproduce
the old architecture's weakness, where the strongest control available was a
well-phrased request.

## What it checks

`lastAssistantText` walks the transcript backwards for the last assistant message,
handling both string and content-block shapes. Then, line by line:

Lines inside fenced code blocks are skipped — code is not a claim. Lines matching an
EXEMPT pattern are skipped: anything already carrying a 🟡 or 🔴 confidence marker (the
claim is already labeled unverified, which is the outcome this hook wants), anything
hedged as a plan or a proposal, anything qualified with "typically" or "by convention",
and checklist items.

What remains is tested against five deliberately narrow CLAIM_SHAPES — a named service
or handler *doing* something, "this is handled/implemented/defined in", "the
configuration sets", "there is/are no X for/in/that", and "the repo uses/has/lacks". They
are narrow on purpose: a general statement about a language or a framework is not a claim
about this repository, and flagging those is exactly how this becomes noise.

A line survives as a gap only if it matches a claim shape and contains no citation, where
a citation is a backticked path, a Markdown link, or a bare `path.ext:line`.

## Action on a hit

A `systemMessage` appended to the turn: the count of uncited claims, up to six of them
quoted and truncated, and an overflow count if there are more. It closes by naming the
two acceptable outcomes — open the file and cite it, or downgrade the claim to 🔴 assumed
and say what would confirm it — and by calling out negative claims specifically.

It appends rather than rewriting the response. Silently editing an agent's output would
hide the failure from the person who most needs to see it.

## Recovery / escape

Nothing is blocked, so nothing needs escaping. The intended response to a gap is to cite
the claim or downgrade it.

To silence it: `ORCHESTRATOR_DISABLED_HOOKS=stop:citation-guard`, or run the `minimal`
profile, which does not include it, or `ORCHESTRATOR_HOOKS_ENABLED=false`.

## Honest limits

It catches five sentence shapes and nothing else. The set of ways to assert something
false about a codebase is very much larger than five, so the claims it misses vastly
outnumber the claims it finds. A gap list of zero means nothing.

The citation test is presence, not correctness. Any backticked filename on the line
satisfies it, so a claim can be laundered by mentioning any file at all, relevant or not.
It never opens the cited file, never checks the line exists, and never checks that the
line says what the sentence says it says.

It reads the last assistant message from the transcript. With no transcript path in the
payload, or an unreadable transcript, it returns silently — no warning, and no
indication that it did not run.

The exempt list is a heuristic in both directions. A hedged sentence that is still a
false claim about the repository passes, and a properly grounded sentence that happens to
contain the word "typically" passes too.

And it fires at `Stop`, after the response is written. It documents the gap; it does not
prevent the claim reaching the user.
