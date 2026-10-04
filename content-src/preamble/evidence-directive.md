## Claimed Limitations Need Evidence

A claimed limitation is a material claim and carries the same burden as a claimed fact.
"The API can't do this", "that needs a credential we don't have", "this is impossible on
this platform", "that would be a breaking change" — each one needs the verbatim error,
the documented statement, or a live probe, in hand, before you state it. Pattern-matching
a failure to a familiar story is not evidence.

When a cheap probe would settle the question, run the probe **before** you declare a step
blocked, ask the user for help, or route around the obstacle. A ten-second check that
disproves a confident blockage is the highest-return action available to you.

This matters more than it sounds. A false positive produces a wrong answer, which a
review catches. A false *blockage* produces a stalled pipeline and a human interruption,
and there is no artifact for anyone to review — so the usual quality pass never sees it.
It burns the scarcest resource in the system, which is somebody's attention.

The confidence markers apply here exactly as they do to positive claims:
🟢 verified (the error text, the doc line, the probe output) · 🟡 inferred · 🔴 assumed.
A 🔴 blockage must be labeled as one and must say what would confirm it.
