# Reference: Build Errors and Silent Failures

> **Progressive disclosure.** This file is not loaded eagerly. Pull in the one section
> you need. A skill that always loads 12K of recipes it uses 5% of the time is a design
> failure, not a rich skill.

---

## Section A — Build Error Recipes

### TypeScript / JavaScript

| Error shape | Usual cause | Fix |
|---|---|---|
| `Cannot find module 'X' or its corresponding type declarations` | Missing `@types/X`, or a path alias not mirrored in `tsconfig.paths` | Install the types, or add the alias to **both** `tsconfig.json` and the bundler config. Fixing one and not the other passes `tsc` and fails at runtime. |
| `Type 'X' is not assignable to type 'Y'` after a version bump | A library widened or narrowed its own types | Read the library's changelog before casting. An `as unknown as Y` here is how a runtime error gets scheduled for three weeks from now. |
| `Object is possibly 'null'` in code that clearly guards | The guard is on a different reference, or `strictNullChecks` cannot see through a callback | Hoist to a local `const`. Do not reach for `!`. |
| `Cannot use import statement outside a module` | ESM/CJS boundary | Check `"type"` in `package.json` and the `module` target. This is a configuration mismatch, never a code problem. |
| Circular dependency warning | Two modules importing each other's types | Extract the shared type to a third module. Type-only cycles still break at runtime under some bundlers. |

### .NET

| Error shape | Usual cause | Fix |
|---|---|---|
| `CS0246: type or namespace could not be found` | Missing project reference, or a `using` not added | Check the `.csproj` reference graph before adding a `using`. |
| `CS8618: non-nullable property must contain a non-null value` | Nullable reference types enabled on an entity class | `required`, a constructor, or `= null!` **with a comment saying why** — an unexplained `null!` is a landmine. |
| `NU1605: package downgrade detected` | Two projects pinning different versions transitively | Unify in `Directory.Packages.props`. Pinning locally hides it until the next restore. |
| Test discovery finds zero tests | Test SDK missing, or the class is not `public` | Check `Microsoft.NET.Test.Sdk` is referenced. **Zero tests found is a failure, never a pass.** |

### Python

| Error shape | Usual cause | Fix |
|---|---|---|
| `ModuleNotFoundError` for a local package | Not installed in editable mode | `pip install -e .`, and check `pyproject.toml` packages discovery. |
| `ImportError: attempted relative import with no known parent package` | Running a module as a script | `python -m package.module`, not `python package/module.py`. |
| `ruff` and the formatter disagree | Two configs, or a stale one | One config in `pyproject.toml`. Two configs is the actual bug. |
| Tests pass locally, fail in CI | Test ordering, or a fixture leaking state | Run with `-p no:randomly` off — if it passes only in one order, the tests share state. |

---

## Section B — The Silent Failure Hunting Checklist

Silent failures are the expensive ones: everything reports success and the behavior is
wrong. Look for these specifically.

1. **An empty catch.** `catch {}` or `except: pass`. Every one is a decision to discard
   information; almost none of them was made deliberately.
2. **A promise nobody awaited.** The function returns, the work has not happened, the
   test passes because it checked too early.
3. **A config read that falls back to a default and logs to nowhere.** The single most
   common cause of "it works on my machine". If a fallback matters, it must be visible
   at the point where somebody would look.
4. **A filter or map that silently drops.** `.filter(x => x.valid)` with no count of
   what was dropped. Log the delta or you will never know it was non-zero.
5. **A comparison across types.** `"1" == 1`, `Guid` vs `string`, a date vs a date-time.
   Passes, matches nothing.
6. **An event handler attached after the event could fire.** Nothing errors; the handler
   just never runs.
7. **A migration that ran on an empty table.** Green in CI, unbounded in production.
8. **A retry with no cap and no backoff.** Turns a transient failure into an outage and
   reports success right up until it does.
9. **A default parameter that is a mutable object.** Python's classic. Shared across
   calls, and the bug appears on the second call, in a different test.
10. **A test asserting on a mock rather than on behavior.** Passes forever, including
    after the real implementation is deleted.
11. **An `if` that can never be false**, usually a truthiness check on an object that is
    always constructed. Dead branch, no warning.
12. **Timezone-naive datetimes crossing a boundary.** Correct locally, off by hours in
    CI, and the difference is invisible in the assertion.

### How to hunt them

Grep for the shapes, do not read for them. `catch\s*\{\s*\}`, `except:\s*pass`,
`\.then\(` without a `return`, `==` in a language where `===` is idiomatic. The point of
a checklist is that it works when you are tired.
