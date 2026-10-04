---
name: destructive-gate
trigger: PreToolUse
matcher: "Bash"
profiles: [standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/destructive-gate.js
description: Classifies every Bash command as allowed, gated, or forbidden, and denies the irreversible ones until their blast radius and rollback are stated.
---

# Destructive Command Gate

Every `Bash` tool call passes through `lib/destructive.js`'s classifier before it runs.
Most commands are classified `allow` and the hook is invisible. The rest fall into two
categories, and the distinction between them is the whole design.

## Why this exists

Some knowledge in this system was already written down and enforced by nothing.
`config/stack-mappings.json` carries entries like `stateWarning: "Never run apply from
an agent context"` — correct, specific, and sitting in a config file that no code
consulted. Prose in a config file is a comment. This gate is the same knowledge, made
into a control.

The failure it prevents is not "the agent is careless." It is that an irreversible
command and a reversible one look identical in a transcript until after they have run.
`terraform apply`, `kubectl delete`, a force-push over `main`, `DROP TABLE` — each is one
line, each executes in under a second, and none of them has an undo. The cost of asking
first is one turn. The cost of not asking is measured in whatever was destroyed.

## What it checks

**FORBIDDEN** — never runs from an agent context. No override, no exempt glob, no
profile that turns it off. Infrastructure mutation (`terraform apply`/`destroy`,
`kubectl delete|apply|replace|drain|cordon`, `helm install|upgrade|uninstall|rollback`,
cloud CLI deletes), history rewriting on a shared branch (`git push --force` without
`--force-with-lease`, any force-push naming a protected branch), data destruction
(`DROP DATABASE|SCHEMA|TABLE`, `mkfs`, `dd` onto a device), taking the machine down, and
a fork bomb. `stackForbidden()` adds whatever the detected stack declared in
`config/stack-mappings.json`.

**GATED** — legitimate but irreversible, so it is denied once and allowed on retry:
`rm -rf` and its PowerShell equivalent, `git reset --hard`, `git clean -f`,
`git checkout -- .`, rebases and history filters, package publishes that cannot be
cleanly unpublished, `gh release create|delete`, truncation, `docker system prune` and
volume removal, and `chmod -R 777`.

Gating is keyed on the *classified pattern*, not the command string. `rm -rf a` and
`rm -rf b` are the same lesson, and gating both teaches nothing the first one did not.

Detection is lexical and conservative on purpose. A shell command is not reliably
parseable, so the classifier errs toward flagging: a false gate costs one turn, and a
missed `rm -rf` costs a workday.

## Action on a hit

For a **forbidden** command, `permissionDecision: deny` with no path forward inside the
agent. The reason states what the command does, says plainly that there is no override
for this class, and redirects to the two things the agent can still do: hand the exact
command to the user to run themselves, or produce the plan, the manifest diff, or the
dry-run output (`terraform plan`, `kubectl diff`, `--dry-run`) and present that for
approval. That is usually the more useful artifact anyway.

For a **gated** command, `deny` with a demand for three things: every file, branch, or
data store it modifies or deletes, enumerated rather than summarized; a one-line rollback
procedure or an explicit statement that there is none; and the user's current instruction
quoted verbatim. Present those and retry the same command. As with the fact-forcing gate,
denials collapse to a single line with an ordinal after three full blocks in a session.

## This handler fails closed

Every other hook in this runtime treats an internal error as ALLOW, because a crashing
gate that blocks all work is worse than one that degrades to the pre-gate world. This
one inverts that: if `classify` throws, the command is denied and the reason says so.

The asymmetry is the point. The recoverable failure here is "the agent had to ask you to
run it yourself." The unrecoverable one is a dropped database.

## Recovery / escape

**Narrow first, and the narrow path is usually the right answer.** Reach for the
reversible form: `git stash` instead of `git reset --hard`, `rm -i` or a move-to-trash
instead of `rm -rf`, `--dry-run` before the real thing. The denial says this explicitly,
because most gated commands have a safer sibling that does the same job.

**Next.** Satisfy the gate — state the blast radius and the rollback — and retry. This
clears the gated tier for that pattern for the rest of the session.

**Broad.** `ORCHESTRATOR_GATEGUARD=off` skips the gated tier, and
`ORCHESTRATOR_DISABLED_HOOKS=pre:bash:destructive-gate` or
`ORCHESTRATOR_HOOKS_ENABLED=false` removes the hook entirely.

**There is no escape for the forbidden tier short of removing the hook.** The
`isDisabled()` check is deliberately placed after the forbidden branch, so
`ORCHESTRATOR_GATEGUARD=off` relaxes the gated commands and leaves the forbidden ones
denied.

## Honest limits

It matches text, not behavior. A command assembled from shell variables, decoded from
base64, aliased, or hidden one level down in a script file is invisible to it —
`bash deploy.sh` passes cleanly whether or not that script runs `terraform apply`. Treat
this as a guard against the fast mistake, not against a determined bypass.

It over-matches too. `\b(shutdown|reboot|halt)\b` will forbid a command that merely
contains the word "reboot" in a string or a path, and `grep -r "drop table" .` classifies
as forbidden. That is the conservative direction of the trade, and it is still wrong when
it happens.

It only sees the `Bash` tool. An MCP server that shells out, a task runner invoked
through another tool, or a script executed by a test harness never reaches this matcher.

The forbidden list is fixed, and dangerous commands are not a fixed set. A destructive
CLI this list has never heard of classifies as `allow`.

And it gates once per pattern per session. The second `rm -rf` of the session runs
without comment, on a different directory than the one you thought about.
