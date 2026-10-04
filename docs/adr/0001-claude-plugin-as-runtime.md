# ADR-0001: The Claude Code plugin is the runtime; the VS Code extension is a view

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** Algoworks AI Platform Team
- **Decision log id:** d-0001

## Context

The predecessor architecture shipped a VS Code extension as the runtime. It loaded the
Markdown content itself, routed slash commands itself, synced content from the hub
itself, and injected context into a chat window that belonged to someone else. Its own
documentation stated the limitation plainly, and the wording is worth quoting because it
is the entire reason this decision exists: the runtime **"does not own the generation
stream."** Grounding was therefore enforced at three points rated Strong, Moderate and
Advisory, and the last of those **"cannot block."**

Every word of that was true. An extension that assembles a prompt and hands it to a chat
window has already spent its only move by the time the model starts producing text. It
can advise. It cannot stop anything.

Two further facts about the predecessor were established by reading its own inventory
rather than by argument. Of its twelve services, five were re-implementations of
platform primitives — skill loading, command routing, content synchronisation, and the
surrounding plumbing — code written to provide capabilities the host now provides
directly. And its install wrote roughly ten paths into every consumer repository, each
of which had to be created, gitignored, upgraded, and eventually removed.

The constraint that changed is a mechanism, not an opinion. A Claude Code `PreToolUse`
hook runs before a tool executes and returns a `permissionDecision` of `"deny"`. That
does not require owning the generation stream; it owns the **action** stream, which is
where a hallucination stops being a sentence and becomes an edit. The reasoning is
recorded at the point of use in `hooks/runtime/handlers/fact-force.js:32-42`. A wrong
paragraph is cheap. A wrong edit to a file whose importers nobody enumerated is not.

The scope this has to carry: 16 skills, 10 agents, 15 executing hooks, 26 commands, 18
eval cases, 4 install profiles. The plugin mechanism requires Claude Code 2.1 or later,
recorded as `plugin.minimumClaudeCodeVersion` in `hub.config.json:21`.

## Decision

Ship the orchestrator as a Claude Code plugin installed from a private GitHub
marketplace repository, and demote the VS Code extension to a read-only view plane that
renders state files and owns no orchestration.

Installation is two commands:

```
/plugin marketplace add algoworks/ai-orchestrator-hub
/plugin install orchestrator@algoworks
```

## Options considered

### Option A — Claude Code plugin distributed through a private GitHub marketplace (chosen)

- **How it works:** `.claude-plugin/plugin.json` declares the plugin;
  `.claude-plugin/marketplace.json` makes this repository a marketplace one command can
  add; `hooks/hooks.json` is auto-loaded by convention and wires the hook
  handlers. Skills, agents, commands and contexts are contributed by the plugin and
  discovered by the host. Hooks run as ordinary Node processes reading a JSON payload on
  stdin and writing a decision on stdout, so a `PreToolUse` handler can deny a tool call
  outright. Updates arrive through the marketplace rather than through a per-repository
  file sync.
- **What it costs:** A hard dependency on one harness and on version 2.1 or later of it.
  Private-repository marketplace authentication is the one part of this we have not yet
  exercised end to end. Contributors must have the plugin installed to reproduce a
  runtime behaviour locally, where previously they could read the extension's source.
- **What it forecloses:** Running the same content under a different agent harness
  without writing a second loader. It does not foreclose running the content by hand —
  the Markdown remains plain Markdown, which is what keeps Option B viable as a fallback
  rather than a rewrite.

### Option B — A setup script that symlinks content into `~/.claude/skills/` (rejected as primary, retained as a secondary path)

- **How it works:** A script clones the hub and creates symlinks from
  `~/.claude/skills/`, `~/.claude/agents/` and the equivalent command directories into
  the clone. The host discovers the content through its normal user-level directories,
  with no marketplace and no network dependency at load time.
- **What it costs:** Everything the plugin mechanism does for free becomes ours to
  maintain and get right: detecting which links we own so an uninstall does not delete a
  colleague's own skills, pruning orphans left behind when a skill is renamed, resolving
  prefix collisions when two sources contribute the same name, Windows symlink semantics
  (which require either Developer Mode or an elevated process, and degrade to copies
  when neither is available), and a migration path for every upgrade that changes the
  layout. The predecessor's ten managed paths per repository are the same class of cost,
  and we know from it that the expensive part is not the install but the uninstall.
- **Why rejected:** Rejected as the primary path because it means owning five mechanisms
  the host already owns correctly, which is the mistake this ADR exists to stop
  repeating. It is **retained as a documented secondary path** for two real cases: an
  air-gapped machine that cannot reach the marketplace, and a team that needs to pin an
  exact hub revision rather than track the marketplace. Those cases are narrow enough
  that the ownership-detection work can be done crudely and reviewed by hand.

### Option C — Publish as an npm package (rejected)

- **How it works:** `npm install -g @algoworks/ai-orchestrator`, with a postinstall step
  that places content where the host will find it.
- **What it costs:** A second identity, a second registry, a second set of credentials,
  and a second place a version number can be wrong. It also does not remove the work in
  Option B — a package still has to place files somewhere and remove them later; it just
  wraps that work in a package manager.
- **Why rejected:** One private organisation repository needs one identity. Adding a
  registry buys distribution we already have from the marketplace and costs an
  authentication surface we would then have to keep in sync with the repository's.

### Option D — Keep the VS Code extension as the runtime (superseded)

- **How it works:** The predecessor architecture: the extension loads content, routes
  commands, syncs from the hub and injects context into the chat window.
- **What it costs:** Grounding that cannot block, by the extension's own account. Five
  services maintained to duplicate platform primitives. Ten managed paths written into
  every consumer repository. An orchestration layer that must track the host's changes
  from the outside.
- **Why rejected:** Superseded rather than argued down. The mechanism its central
  limitation was stated against no longer holds, and roughly five of its twelve services
  became re-implementations of things the host does natively. Those are deleted rather
  than ported. What survives is genuinely useful and genuinely a view: reading state
  files and showing them in the editor, which the terminal cannot do.

### Option E — Commit a `.claude/` directory into every consumer repository (rejected as primary, retained for overrides)

- **How it works:** Each repository carries its own copy of the skills, agents and hooks
  it needs, checked in alongside its code.
- **What it costs:** The hub is duplicated into every repository, and every repository's
  copy drifts on its own schedule. A fix to a hook has to be landed once per repository
  by whoever remembers which ones have it.
- **Why rejected:** Duplicating the hub into every repository is the exact problem the
  hub exists to solve, so choosing it as the primary mechanism would leave us maintaining
  a distribution system that distributes nothing. It is **retained for per-repository
  overrides**, which is what a repository-local `.claude/` is genuinely good at: one
  team's extra hook, one repository's stricter gate, expressed where it applies and
  nowhere else.

## Strongest argument against this decision

This ties the entire system to a single vendor's harness, at a specific minimum version,
through a distribution mechanism we have not yet proven works for a private repository.

Every capability that makes this architecture better than its predecessor — denying a
tool call, contributing skills the host discovers, hooks that fire on session start and
pre-compaction — exists because Claude Code provides it. If that surface changes shape,
we do not degrade gracefully; the gates stop firing, and a gate that stops firing does
not announce itself. The minimum-version requirement means a colleague on 2.0 does not
get a warning, they get an install that does nothing useful. And the one operational
unknown is not a peripheral one: if private-repository marketplace authentication turns
out to require a token flow that our developers cannot complete on a managed laptop, the
chosen option's install story collapses to Option B's, with the plugin layout already
committed.

The honest answer is that the content plane is portable — it is Markdown, and Option B
exists precisely so that "run this without a marketplace" remains a script rather than a
rewrite — but the enforcement plane is not. The hooks are the reason this system is
worth having, and they are the part that does not port.

## Consequences

- **Positive:** Grounding moves from Advisory to blocking, because a `PreToolUse` hook
  denies the tool call rather than advising the prose. Five services are deleted rather
  than maintained. The paths written into a consumer repository drop from roughly ten to
  two — see `scripts/orchestrator.py:55-62`, where `MANAGED_PATHS` is now the repository
  context file and the install record, and nothing else. Upgrades arrive through one
  marketplace update instead of a per-repository sync. The view plane gets smaller and
  its boundary becomes checkable, which `check_plane_separation` in
  `scripts/validate-structure.py` now enforces.
- **Negative:** A hard floor of Claude Code 2.1. No graceful degradation if the plugin
  or hook surface changes. Private-marketplace authentication is unverified. Anyone
  reproducing runtime behaviour needs the plugin installed, not just the repository
  cloned. Two install paths (plugin and script) means two things that can be
  inconsistent, and the secondary one will be exercised rarely enough to rot quietly.
- **Reversal cost:** An estimate, not a measurement — nothing here has been timed. The
  content plane does not move: skills, agents, commands and contexts are Markdown and
  would be read by whatever came next. The hook handlers are plain Node reading JSON on
  stdin, so the handler bodies survive; what would have to be rebuilt is the wiring —
  a loader, a dispatcher, and whatever the replacement host offers in place of
  `permissionDecision`. Call it several days of one engineer's time if a comparable
  blocking mechanism exists in the replacement, and a genuine redesign if it does not,
  because the system's central claim would no longer be true. Blast radius on reversal is
  every connected repository at once, since the install is machine-scoped rather than
  per-repository: everyone re-installs on the same day.

## Follow-ups

- **Verify private-repository marketplace authentication before the layout is
  committed.** Create a throwaway private repository containing only
  `.claude-plugin/marketplace.json` and a single trivial skill, and run
  `/plugin marketplace add` against it from a machine that has never authenticated to
  it. This is the one operational unknown in the decision, and it is cheap to close.
  Owner: AI Platform Team, before the first team-wide install.
- **Document the secondary install path (Option B) as a supported fallback**, with its
  ownership-detection and Windows symlink caveats stated rather than discovered. An
  undocumented fallback is not a fallback. Owner: AI Platform Team.
- **Record this decision in the decision log**, which is what makes it findable by an
  agent in four months. An ADR that is not in the log is a diary entry:

  ```
  python scripts/decision.py log \
    --decision "Ship the orchestrator as a Claude Code plugin; the VS Code extension becomes a read-only view plane" \
    --rationale "A PreToolUse hook can deny a tool call, so grounding stops being advisory; five of twelve predecessor services were re-implementations of platform primitives" \
    --alternatives "Symlink script (kept as a secondary path), npm package, VS Code extension as runtime (superseded), committed .claude/ per repo (kept for overrides)" \
    --adr docs/adr/0001-claude-plugin-as-runtime.md
  ```

  The `d-0001` above is reserved, not yet recorded. Ids are assigned by insertion order
  — `next_id` in `scripts/decision.py` counts the existing `decide` events — so log this
  decision before ADR-0002's, or the numbers in the two files will not match the log.
