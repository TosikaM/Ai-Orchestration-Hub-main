# Third-Party Notices

This repository is proprietary, and it is not a fork of anything. It does, however, adapt
design patterns from two MIT-licensed projects, and one file in it is closely derived from
a specific source file. Attribution is owed in both cases, for different reasons, and this
document distinguishes them rather than blurring them into a single acknowledgement.

## Two categories, and why the distinction matters

**Adapted patterns.** A design idea was read, understood, and re-implemented here in a
different language against a different data model. No source lines were copied. The MIT
license does not compel attribution for an idea expressed in independent code — but naming
the source is what a professional does, and it is also the more useful engineering artifact:
a future maintainer who wants to know why the denial budget collapses to one line after
three blocks is better served by a pointer to the original than by a paraphrase of it.

**Closely-derived code.** The structure, the control flow and the wording of one file
follow its source closely enough that treating it as independent work would be a
misrepresentation. That file is treated as derived: it carries the full MIT header inline
so the notice travels with the code even if this document is separated from it.

Exactly one file falls into the second category. Everything else below is the first.

---

## 1. ECC

- **Project:** ECC
- **Copyright:** Copyright (c) 2026 Affaan Mustafa
- **License:** MIT

### What was adopted

| Pattern | Where it lives here |
|---|---|
| The **fact-forcing gate** design — first touch per file per session, the four demanded facts, the denial budget that collapses repeated blocks to a one-line ordinal, and narrow recovery offered before broad recovery | `hooks/runtime/handlers/fact-force.js`, `hooks/fact-force.hook.md` |
| The **hook profile model** — named profiles, a global kill switch, per-hook surgical disable, and an invalid profile falling back to the default rather than to off | `hooks/runtime/flags.js`, `hooks/runtime/registry.json` |
| The **install-state shape** — recording the install *request* alongside the files written, so a repair can re-derive intent rather than guess at it, and recording invisible side effects as first-class operations | `scripts/orchestrator.py`, `.github/orchestrator-install.json` |
| The **confidence arithmetic** for memory — a numeric source for a promotion rule that previously had none, with reinforcement, counter-example and decay terms | `scripts/memory.py`, `memory/README.md` |
| The **MCP health check** before a connector tool call | `hooks/runtime/handlers/mcp-health.js` |
| The **session lifecycle mapping** — which work belongs at `SessionStart`, `PreCompact`, `Stop` and `SessionEnd` | `hooks/runtime/registry.json`, `hooks/hooks.json` |

### The derived file

`hooks/runtime/handlers/fact-force.js` is closely derived from ECC's
`scripts/hooks/gateguard-fact-force.js`. It carries the full MIT license text as an inline
header comment, so the notice stays attached to the code. Do not remove that header when
editing the file; if the file is ever rewritten to the point where the derivation no longer
holds, that is a decision to record in an ADR rather than a header to quietly delete.

ECC's own header credits **GateGuard** as its upstream:
<https://github.com/zunoworks/gateguard>. That credit is carried forward here for the same
reason ECC carried it: the chain is part of the attribution, not a footnote to it.

### License

```
MIT License

Copyright (c) 2026 Affaan Mustafa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. gstack

- **Project:** gstack
- **Copyright:** Copyright (c) 2026 Garry Tan
- **License:** MIT

### What was adopted

| Pattern | Where it lives here |
|---|---|
| The **budget ratchet** — measured ceilings carrying their own provenance, a written re-derivation protocol, and mutation pins on the guard itself so a ceiling cannot be disabled by turning it into a string | `config/token-budgets.json`, `scripts/measure-discovery-budget.py`, `check_budget_provenance` in `scripts/validate-structure.py` |
| The **context bill of materials** — always-on cost accounted separately from per-invocation cost, with `--diff` and `--budget` modes | `scripts/context-bill.py` |
| **`allowed-tools` least privilege per skill**, enforced rather than declared, including the read-only verifier rule | `check_allowed_tools` in `scripts/validate-structure.py`, every `skills/*/SKILL.md` |
| The **two-tier, diff-selected eval harness** and its strict-output contract — a case that produced no parseable verdict is FAILED, never skipped and never passed, and the diff selector fails *open* | `evals/eval-runner.py`, `evals/evals.json`, `evals/touchfiles.json` |
| The **redaction taxonomy and tier calibration** — three tiers, scoped suppressions, the rule that repository visibility never promotes a tier, and the linear-time regex requirement | `config/redaction-patterns.json`, `scripts/redact.py`, `lib/redact.js` |
| The **egress receipt design** — content-free, hash-chained, written before the send, with declared per-sink polarity | `scripts/egress-receipt.py` |
| The **ownership gate** — never remove a file you cannot prove you created, verified by hash | `cmd_uninstall` in `scripts/orchestrator.py` |
| **Upgrade migrations** — numbered scripts applied in order and recorded, stopping at the first failure | `migrations/`, `cmd_upgrade` in `scripts/orchestrator.py` |

A note on what these have in common, because it is the actual contribution: none of them is
a feature. Each one is a way of making a claimed guarantee *checkable*. This system declared
a token economy and a grounding standard as principles before it had anything that could
falsify either claim; the patterns above are what turned those declarations into things a
build can fail on.

### License

```
MIT License

Copyright (c) 2026 Garry Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Runtime dependencies

The content plane depends on the Python standard library plus **`pyyaml`** (MIT), and
nothing else. That constraint is deliberate: the content plane has to be buildable and
checkable without entering a package manager, and every dependency added to
`scripts/_lib.py` is one a consumer repository's CI must install before it can run a
validation that is supposed to be cheap.

The hook runtime depends on the Node.js standard library only — no `node_modules` at
runtime. The view plane has its own dependencies, declared in `view/package.json` and
installed from its lockfile; they affect the optional VS Code extension and nothing else.

## Adding to this file

If you adopt a pattern from an outside project, add it here in the same commit, with the
same distinction: name the pattern, name where it lives in this repository, and say whether
it is adapted or derived. If it is derived, put the license header in the file as well —
this document can be separated from the code, and a header cannot.
