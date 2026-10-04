# Reference: Security Checklists, Per Pass

> **Progressive disclosure.** Load the one section the review needs. This file is large
> by design and eager loading would spend the budget the whole system exists to protect.

Every entry below is a *candidate*. A candidate becomes a finding only when you can state
the input an attacker controls, the route it travels, and the outcome. Severity without a
scenario is a suggestion — file it as one.

---

## Pass 1 — Credential Exposure

| Language | Pattern to grep | Note |
|---|---|---|
| All | `api[_-]?key\s*[:=]`, `secret\s*[:=]`, `password\s*[:=]` | Then check whether the value is a literal or a lookup |
| TS/JS | `process.env.X \|\| "literal"` | The fallback is the leak |
| C# | `ConnectionString = "..."`, `IConfiguration` with an inline default | |
| Python | `os.getenv("X", "literal")` | Same shape as the JS one |
| Go | `const token = "` | |
| All | Secrets written to logs: `log(.*token`, `console.log(.*key` | The most common real finding |

**False positives to skip:** test fixtures with obviously dummy values, `.example` files,
documented example values, framework-standard constants, and anything matching a
placeholder shape (`YOUR_KEY_HERE`, `xxx`, `<TOKEN>`).

**But note:** a real credential in a test file is still a real credential. Test paths
suppress MEDIUM and LOW findings, never HIGH.

---

## Pass 2 — Injection Surfaces

| Kind | TS/JS | C# | Python | Go |
|---|---|---|---|---|
| Shell | `exec(` / `execSync(` with template literals | `Process.Start(string)` | `os.system`, `subprocess` with `shell=True` | `exec.Command("sh","-c",…)` |
| SQL | string-concatenated query | `SqlCommand` with interpolation | f-string in `cursor.execute` | `fmt.Sprintf` into a query |
| Path | `path.join(base, userInput)` with no containment check | `Path.Combine` likewise | `os.path.join` likewise | `filepath.Join` likewise |
| Template | `dangerouslySetInnerHTML`, `v-html` | `Html.Raw` | Jinja `\| safe` | `template.HTML` |
| Prototype | `Object.assign({}, userJson)` onto a shared object | — | — | — |

For path traversal the test is containment, not sanitization: resolve the joined path and
assert it is still inside the base. Blocklisting `..` is defeated by encoding.

---

## Pass 3 — Unsafe Subprocess

The rule: **an argv array, never a string.**

```ts
// wrong — one space in a filename and this is a different command
execSync(`git update-index --skip-worktree ${paths.join(' ')}`);

// right
execFileSync('git', ['update-index', '--skip-worktree', ...paths]);
```

Also check: argument lists built from repo-derived values must be chunked (a few hundred
paths will exceed the command-line limit and the failure is confusing), and every
`shell: true` needs a comment explaining why it is safe.

---

## Pass 4 — Deserialization and Dynamic Evaluation

| Language | Dangerous | Safe replacement |
|---|---|---|
| Python | `pickle.load`, `yaml.load`, `eval`, `exec` | `json`, `yaml.safe_load`, a dispatch dict |
| TS/JS | `eval`, `new Function`, `vm.runInThisContext` | `JSON.parse`, a lookup table |
| C# | `BinaryFormatter`, `TypeNameHandling.All` | `System.Text.Json`, no polymorphic type resolution |
| Java | `ObjectInputStream` on untrusted bytes | A schema-driven parser |

`yaml.load` without a loader is the one that most often ships. It executes constructors.

---

## Pass 5 — Authentication and Authorization Gaps

For every new or changed endpoint:

1. Is there an authentication attribute or middleware on this route, or is it inheriting
   one? Inheriting is fine — **verify it, do not assume it.**
2. Is there an authorization check, and does it check the *resource*, not just the role?
   Role-only checks are how one user reads another's record with a valid token.
3. Does the identifier come from the token or from the request body? From the body is
   the bug.
4. Does the error path leak whether the resource exists? A 403 for "exists but yours" and
   a 404 for "does not exist" is an enumeration oracle.

---

## Pass 6 — Dependency Risk

- New dependency: who publishes it, how many versions, when was the last one, does the
  name resemble a popular package by one character?
- Bumped dependency: read the diff of the changelog, not the version number.
- A transitive addition that arrives with a direct one is still a new dependency.
- Lockfile changes with no manifest change deserve a look — that is either a legitimate
  resolution update or something else.

---

## Pass 7 — Secrets in Configuration and CI

- Workflow files with a literal in an `env:` block
- A `secrets.X` reference that is echoed into a log step
- `.env` committed, or `.env.example` containing a real value someone forgot to blank
- Docker `ARG`/`ENV` carrying a token — these persist in image layers even if later unset
- A `--build-arg` in a documented command

---

## Pass 8 — Agent Surface Audit

The reframe: **agent configuration is an attack surface, and it is one this system
generates and distributes.** Every other pass looks at the consumer's code. This one
looks at what the orchestrator wrote into the consumer's repository — which is the
highest-privilege text there, because it goes straight into a model's instructions.

Run `python scripts/audit-agent-surface.py`. It checks:

1. Every `.github/agents/*.agent.md` carries the Prompt Defense Baseline
2. Every `.github/skills/*/SKILL.md` declares `allowed-tools`
3. No hook command string interpolates a repo-derived value
4. No MCP connector is declared that is absent from `tool-registry.json → defaults`
5. No synced file matches an injection signature
6. Every operation in `.github/orchestrator-install.json` verifies

The second path worth naming: shared memory is written from agent output and syncs
organization-wide. A prompt-injected response in one repository writes a learning that is
re-injected as context in every other repository. That is self-propagation, and it is why
the memory write path scans before it writes.
