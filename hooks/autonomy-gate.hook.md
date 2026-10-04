---
name: autonomy-gate
trigger: PreToolUse
matcher: "Edit|Write|MultiEdit|Bash|PowerShell"
profiles: [minimal, standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/autonomy-gate.js
description: Denies any action whose blast radius exceeds the autonomy level this repository is permitted to operate at.
---

# Autonomy Gate

Runs before every write and every shell command. It resolves the autonomy level from
`config/policy.json` and refuses actions the level does not permit.

## Why this exists

A safety kernel bounds how **long** an agent runs — five iterations, fifty thousand
tokens, ten minutes, stop on a stall. Every one of those is a limit on effort.

None of them is a limit on **blast radius**, and blast radius is what a customer actually
asks about. An agent that runs for nine seconds and pushes to `main` has stayed
comfortably inside every kernel limit. The kernel was never the control for that.

So autonomy becomes an explicit, resolved level:

| Level | Name | What it permits |
|-------|------|-----------------|
| 0 | explain only | No writes at all. Describes and proposes. |
| 1 | suggest code | Diffs are shown, never applied. |
| 2 | write code | Edits land in the working tree; each needs approval. |
| 3 | write, test, self-correct | Iterates inside a repository. No branch, no PR, no deploy. |
| 4 | open a pull request | An artifact goes in front of colleagues. |
| 5 | deploy | Something customers touch changes. |

The default ceiling is **3**, and it sits there for a specific reason rather than as a
middle value: the jump in blast radius between 3 and 4 is much larger than between any
other adjacent pair. Below 4, a mistake stays in a working tree somebody has to look at
before it goes anywhere. At 4 it enters a review queue wearing a plausible description,
where the reviewer's attention is the only thing between it and `main`. At 5 it is in
production.

## What it checks

| Action | Minimum level |
|--------|---------------|
| `Edit` / `Write` / `MultiEdit` / `NotebookEdit` | 2 |
| `git push` | 4 |
| `gh pr create` | 4 |
| `gh pr merge` | 5 |
| `kubectl`, `helm`, `terraform`, `serverless`, `flyctl`, `vercel`, `netlify` | 5 |
| `docker push`, `npm publish`, `dotnet nuget push` | 5 |

Independently of level, a write to any path matching
`dataPolicy.forbiddenPathGlobs` — `.env`, `secrets/**`, private keys, `.aws/`,
`.kube/config` — is refused. That is not a blast-radius question. Credential material is
out of bounds at every level, including 5.

## Action on a hit

Denies, and says which level is required, which level is in force, and what the
level-appropriate version of the work looks like: produce the branch contents, the PR
body, or the deployment plan as an artifact and hand it to a human.

The denial deliberately does **not** read as retryable. Rephrasing will not clear a
policy limit, and a gate whose message invites another attempt gets another attempt.

## Recovery

Raising the level is a human decision, and it is recorded:

```
python scripts/policy.py autonomy      # what the levels mean for this repository
python scripts/decision.py log --decision "raise autonomy to 4 for <repo>" --rationale "..."
```

**A repository cannot raise its own level.** `scripts/policy.py` refuses a widening from
a narrower layer, so a repo-local policy file may only restrict what its project allows.
Policy lives in files an agent can edit, and an agent optimizing for "make the task
complete" will find `autonomy.level` eventually — the narrowing rule is what makes
finding it useless.

## Why this is separate from config-protection and destructive-gate

Three gates, three different questions, and merging them would produce denials too vague
to act on:

- `config-protection` asks *is this file a gate?*
- `destructive-gate` asks *is this command irreversible?*
- this one asks *is this class of action permitted at the level we are operating at?*

A `git push` is neither a governance file nor destructive, and at level 3 it is still
forbidden. Only this gate has that answer.

## Fails closed

Unlike most of this runtime — which treats a handler error as ALLOW so a bug in a hook
cannot stop all work — this gate denies when the policy cannot be resolved.

The asymmetry is deliberate and matches `destructive-gate`. If an organization has
narrowed autonomy and that narrowing cannot be read, running on the shipped defaults
would grant precisely what somebody deliberately withheld. The recoverable failure is
"run `python scripts/policy.py resolve`". The unrecoverable one is a deploy nobody
authorised.

The one exception: when `config/policy.json` is absent entirely, the gate allows. A
system with no policy shipped is not a system with a policy that failed to load, and
refusing every action because an optional file is missing would be a poor first
experience.

## Honest limits

- **Detection is lexical.** It matches command shapes, so `eval "$DEPLOY_CMD"` or a
  wrapper script named `./ship` will pass. This raises the cost of an accident; it does
  not stop a determined route around it. The controls that matter for that are the
  credentials on the machine and the branch protection on the repository.
- **It does not know what a tool will do**, only what it is called. A custom script that
  deploys is invisible to it until someone adds it to `LEVEL_REQUIRED`.
- **Level 2 versus 3 is not enforced here.** Both permit writing; the difference is
  whether each edit needs approval, and that is the fact-forcing gate's and the human
  gate's job, not this one's.
- It reads a **cached resolution**. If `scripts/policy.py resolve` has not been run since
  a policy change, the gate is enforcing the previous policy — which is why it refuses
  rather than guesses when narrowing layers exist and no cache does.
