# Security

## Reporting a vulnerability

Report privately. Open a draft security advisory on the hub repository
(`abhishek-narula-algoworks/Ai-Orchestration-Hub` → **Security** → **Report a vulnerability**), which
creates a private thread visible only to the maintainers. If advisories are unavailable to
you, contact the platform team directly at the GitHub handle
[`@algoworks/ai-platform`](https://github.com/orgs/algoworks/teams/ai-platform) — the same
team named in `.github/CODEOWNERS` for `/config/`, `/hooks/` and `/scripts/`.

**Do not open a public issue for a security report.** This repository is a distribution
channel: content merged here loads into other people's sessions on their next prompt, with
no staging step in between. A public report is a public exploit against every connected
repository at once.

If your organization publishes a dedicated security mailbox, it belongs in
`hub.config.json` under the `org` block rather than in this file. Organization identity is
data here, not text (design principle P3), and this document is meant to be reusable by
another team without an edit.

Please include what you can reproduce: the version from `hub.config.json` → `hub.version`,
the hook profile in effect, and whether the behaviour reproduces with
`ORCHESTRATOR_HOOKS_ENABLED=false`. That last one separates a runtime-plane problem from a
content-plane one in a single step.

## Supported versions

| Version | Status |
|---|---|
| **3.1.x** | Supported. The Claude Code plugin architecture; this is the line that receives fixes. |
| 3.0.x and earlier | Not supported. The VS Code extension runtime was superseded rather than deprecated: it is a different architecture with a different threat model, and the guarantees described below do not apply to it. |

Upgrade with `/plugin marketplace update` followed by
`python scripts/orchestrator.py upgrade` in each connected repository, which runs the
numbered migrations in order.

---

## Threat model, in plain terms

This tool does four things that matter to a security reviewer, and it is worth stating them
without hedging:

1. **It reads your repository.** Source, configuration, git history, and whatever else an
   agent decides is relevant to the task.
2. **It writes into `.github/`.** Exactly two paths — `orchestrator-context.md` and
   `orchestrator-install.json` — recorded in install state so an uninstall can reverse
   precisely what it created and nothing else.
3. **It shells out to `git`.** For install state, `skip-worktree` bits, diff selection in
   the eval harness, and the structural index.
4. **It may clone a configured hub repository.** That clone pulls **executable content**:
   `SKILL.md` files and agent definitions that steer an agent's behaviour once loaded.

Point 4 is the one that is different in kind from the others, and it gets its own section
below.

What this tool does **not** do: it does not phone home, it does not upload your source
anywhere by itself, and it holds no credentials of its own. Every off-machine action it
takes is one you configured — a `git` remote, or an MCP connector your organization
enabled.

---

## Hardened surfaces

Each of the following is a place where a plausible implementation would have been unsafe,
and the safe version is the one that shipped.

**`git` is invoked with an argv array, never a formatted shell string, and path lists are
chunked at 100.** A filename containing a space in a string-built command is a *different
command*, and this system passes paths derived from repository contents. The chunking is
the less obvious half: a few hundred paths exceeds the platform command-line limit and
fails with an error that does not name the cause, which is exactly the kind of failure that
gets "fixed" by falling back to a shell string. See `scripts/gitignore.py`.

**Webviews escape every interpolation and set a nonce content security policy.** The
gate-review panel renders a pipeline artifact — text produced by an agent, quite possibly
from a file somebody else wrote. Every interpolation is HTML-escaped through `escapeHtml`,
and the policy is `default-src 'none'` with a per-render nonce for the one stylesheet.
Rendering agent output into a webview without both is script execution inside the editor's
trust boundary.

**Every string written to shared memory, a repository context file or a release artifact is
scanned before the write, and a HIGH-tier credential blocks it.** Not sanitizes — blocks.
A silently redacted resolution reads as complete, so nobody goes back to fix it, and the
real credential is still wherever it came from. Sinks declare their own polarity in
`config/redaction-patterns.json`: `memory.shared.write`, `memory.decision.write`,
`context.file.write`, `release.artifact.write` and `hub.clone` are fail-closed;
`chat.stream` is fail-open, because blocking a developer's primary interaction over a scan
is the worse outcome (P5).

The taxonomy is calibrated rather than maximal. Only genuinely-secret credentials are HIGH,
because a gate that cries wolf gets ignored and an ignored gate is worse than none.
Repository visibility never promotes a tier — a public repository earns sterner
confirmation on MEDIUM findings, it does not turn MEDIUM into HIGH. Suppressions are
scoped: the placeholder suppression matches the matched span rather than the line, so a
real key on the same line as the word "example" still counts, and the test-fixture
suppression applies to MEDIUM and LOW only, because a HIGH-tier credential in a test file
is still a HIGH-tier credential — that is where they most often get committed.

Every pattern must be linear-time, checked by `python scripts/redact.py --lint` in CI. A
catastrophically backtracking regex does not fail loudly; it hangs the egress path, and the
natural workaround is to switch redaction off.

**Every off-machine send writes a content-free, hash-chained receipt before the send.**
`scripts/egress-receipt.py` records a sha256 of the exact bytes plus a byte count — never
payload text, because a ledger that stored payloads would itself become the leak — and each
line carries `prev` = sha256 of the previous raw line, so a deletion or an edit is
detectable without making the log immutable. Fail-closed sinks refuse the send when the
receipt cannot be written.

**Read the ledger's limit as part of the ledger.** It is **forensic observability, not an
exfiltration control.** It records what was attempted so an accident is auditable; a
determined leaker bypasses it trivially. What it catches is carelessness, which is the
common case and the case the redaction gate is also aimed at. This sentence is in the
source file as well, because a ledger described as a security control gets trusted as one,
and then somebody decides a second control is unnecessary "because we have the ledger."

**Two guards are exempt from the hook profile system.** Prompt defense and the memory
redaction guard run at every profile, including `minimal`. A profile is a convenience dial
for friction, not a security dial, and disabling a guard by choosing a lighter profile
would be a footgun disguised as a preference. The global kill switch
(`ORCHESTRATOR_HOOKS_ENABLED=false`) still turns off the entire runtime — one obvious
switch rather than a hidden one.

**The memory write guard is a function, not a hook.** Modeling it as an event would leave
the write path unguarded on every occasion the event failed to fire, turning a wiring bug
into a security hole. The call site is the only way in and there is no `--force`.

---

## Supply chain: the primary risk

**A malicious `SKILL.md` from a compromised hub is the highest-consequence attack against
this system.** It is not a code-execution bug; it is the channel working as designed. The
hub is an automatic, on-open, unattended distribution channel for Markdown that goes
straight into an agent's instructions, and there is no human between a merge and a
colleague's next session.

There is a second, closer path that makes it worse. Learning capture writes agent *output*
into shared memory, and shared memory syncs organization-wide. A prompt-injected response
in one repository can write a learning that is re-injected as context in every other
repository. That is self-propagation, and it is why the memory write path scans for
injection markers and refuses rather than sanitizing.

Three layers now stand in the way, where the previous architecture named this an accepted
risk with no mitigation:

**1. Scanned and quarantined at the sync boundary.** `scripts/sync-repo.ps1` and the hub
sync path scan Markdown for prompt-injection signatures before writing it into a consumer
repository, and quarantine on a hit. The file never lands, so it never reaches a model.
This is the layer that actually removes the exposure rather than annotating it.

**2. Every agent carries a stated identity boundary.** The `## Prompt Defense Baseline`
section is rendered into every agent from `content-src/preamble/prompt-defense.md`, and
`scripts/validate-structure.py` fails the build on an agent that lacks it. The boundary
says repository content is **data**: instructions found inside a file are reported, not
followed, and the original task continues.

**3. A `PreToolUse` hook flags reads of synced paths matching an injection signature.**
`hooks/runtime/handlers/prompt-defense.js` watches the paths whose content arrives from the
hub or from another agent's output — reading anything else is reading your own repository,
which is a different trust story. It **flags rather than blocks**, deliberately: the agent
may legitimately need to inspect a poisoned file, and quite often that *is* the task. So it
prepends a warning to what the model sees, which changes how the content is read without
preventing the read.

### The honest closing, which is the part that matters

**None of these three layers is complete.** They pattern-match on the shapes injection has
taken so far — "ignore previous instructions", "you are now", a fake `<system>` tag, a
"BEGIN SYSTEM PROMPT" banner. A sufficiently subtle instruction embedded in plausible
protocol text will pass all three: a `SKILL.md` that reads like a legitimate step in a
legitimate workflow, phrased as guidance rather than as a command, matches no signature and
triggers no guard.

**Reviewing the hub repository is still the control that matters most.** The layers above
reduce the blast radius of a compromise that gets past it; they do not replace it. Code
review on `content-src/` and `skills/`, branch protection on the hub's default branch, and
the `CODEOWNERS` assignment on `/content-src/preamble/` — the directory whose contents are
rendered into every agent in every connected repository — are what actually stand between a
compromised account and an organization-wide instruction change.

Two operational consequences follow from that, and they are worth doing rather than
reading:

- Treat a pull request that touches `content-src/preamble/`, `skills/*/SKILL.md` or
  `agents/` as a change to every connected repository, because it is one.
- Verify that "Require review from Code Owners" is actually enabled on the hub's protected
  branch. No workflow in this repository can check that — it is a repository setting, not a
  file — and `.github/workflows/governance.yml` says so in those words rather than
  implying a green check covers it.

---

## Known limits, collected

Stated together so nobody has to reconstruct them from three sections:

- The egress ledger is forensic observability, not an exfiltration control.
- The injection defenses are signature-based and incomplete; hub review remains the primary
  control.
- The grounding manifest is lexical. It cannot catch a wrong claim about a file that exists
  and was genuinely read.
- A hook that cannot run contributes no decision, and the session continues as though the
  gate allowed the action. A missing Node runtime silently removes every gate. CI parses
  every handler for exactly this reason, but CI cannot check the machine the plugin is
  installed on — `python scripts/orchestrator.py doctor` is the local equivalent.
- The system depends on one harness at a minimum version. If Claude Code's hook surface
  changes shape, the gates stop firing, and a gate that stops firing does not announce
  itself.
