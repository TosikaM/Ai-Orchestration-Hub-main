# Python — Modern Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below. So does `requires-python` in `pyproject.toml`: `match` needs 3.10,
> `TaskGroup` and `asyncio.timeout` need 3.11, `Path.walk` needs 3.12. Proposing syntax the
> project's floor cannot parse costs a full round trip — read the floor first and say which
> version you read.

## `pyproject.toml` as the single file

One file holds the metadata, the dependencies, and the configuration of every tool that
supports it. `setup.py`, `setup.cfg`, `requirements.txt`, `.flake8` and `.isort.cfg` are all
absorbed, and the reason that matters is not tidiness — it is that a tool reading a file
nobody remembers is how two linters end up disagreeing in CI.

```toml
[project]
name = "orders"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.115", "pydantic>=2.7", "httpx>=0.27"]

[project.optional-dependencies]
postgres = ["asyncpg>=0.29"]        # a feature a consumer may want

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio", "ruff", "pyright"]   # never installed by a consumer

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
addopts = "-q --strict-markers --strict-config"
```

Keep the distinction between the two dependency blocks deliberate. `optional-dependencies`
are extras a *consumer* can install (`pip install orders[postgres]`); development tools are
not that, and publishing them as an extra means anyone can install your test suite's
dependencies by accident. `[dependency-groups]` (PEP 735) is the standard home for them, but
installer support arrived at different times — confirm the project's installer understands
it before moving a `dev` extra across.

Pin `requires-python` to what you actually test. A floor of `>=3.8` that CI never exercises
is a claim, not a guarantee.

## `ruff`

`ruff check` replaces flake8, isort, pyupgrade, and most of the plugin ecosystem; `ruff
format` replaces black. One tool, one config block, one pass over the tree — and, more
usefully, one place where a rule can be turned off with a reason next to it.

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF", "ASYNC", "PTH"]
ignore = ["E501"]              # the formatter owns line length

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]           # assert is the point of a test
```

`B` (bugbear) catches the mutable-default-argument trap from `python-patterns.md` before
review does; `ASYNC` catches blocking calls inside coroutines; `PTH` flags `os.path` usage
that `pathlib` does better. Suppress with a specific code and a reason —
`# noqa: B008 -- FastAPI evaluates Depends() at call time` — never a bare `# noqa`, which
disables every rule on that line including the ones added next year.

`ruff format` is Black-compatible in intent but not byte-identical in every edge case, so
migrate in one commit that touches formatting only — a reformat mixed into a feature branch
makes the diff unreviewable.

## Structural pattern matching

`match` earns its place when you are **destructuring** — pulling a shape apart and binding
its parts. A chain of equality checks is clearer as `if`/`elif`, and rewriting one as a
`match` makes it longer without making it safer.

```python
match event:
    case {"type": "order.created", "id": str(order_id), "lines": [_, *_] as lines}:
        handle_created(order_id, lines)
    case {"type": "order.cancelled", "id": str(order_id), "reason": reason} if reason:
        handle_cancelled(order_id, reason)
    case _:
        logger.warning("unhandled event", extra={"event_type": event.get("type")})
```

Mapping patterns match a **subset** of keys, so extra keys do not prevent a match — which is
what makes this safe against additive changes to an upstream payload. Class patterns match
on type and then on attributes, and the positional form works only for classes that define
`__match_args__` (dataclasses and `NamedTuple` do, automatically).

**The one trap that costs an afternoon:** a bare name in a pattern is a *capture*, not a
comparison. It matches anything and rebinds the name.

```python
match status:
    case PENDING:          # matches EVERYTHING and rebinds PENDING
        ...
    case OrderStatus.PENDING:   # a dotted name is a value pattern -- this compares
        ...
```

Always compare against a dotted name — an enum member, a module constant — and let the
final `case _` handle the rest. Ruff's `E` and pattern-related rules will not always catch
this, because the code is legal; it simply means something other than what it looks like.

## Async patterns

```python
async def load_dashboard(customer_id: UUID) -> Dashboard:
    async with asyncio.timeout(5):
        async with asyncio.TaskGroup() as group:
            orders = group.create_task(fetch_orders(customer_id))
            profile = group.create_task(fetch_profile(customer_id))
    return Dashboard(orders.result(), profile.result())
```

- **`TaskGroup` over `gather`** (3.11+). When one child fails, the group cancels its
  siblings and raises an `ExceptionGroup` at the `async with` — nothing is left running. With
  `gather(..., return_exceptions=False)` the sibling keeps going after the first failure and
  its eventual exception is reported as "never retrieved", which is a warning on stderr
  rather than an error anyone handles.
- Handle grouped failures with `except*`, which receives every matching exception in the
  group rather than only the first.
- **`asyncio.timeout`** as a context manager beats `wait_for` around a call: it wraps a block,
  it composes with `TaskGroup`, and cancellation propagates into everything inside it.
- **Never call blocking code in a coroutine.** `requests`, `time.sleep`, `open().read()` on a
  slow disk, and any CPU-heavy loop stall the whole event loop, so the symptom is every
  unrelated request getting slower at once. Wrap with `await asyncio.to_thread(fn, *args)`,
  or use an async client.
- **Keep a reference to every fire-and-forget task.** The event loop holds only a weak
  reference, so a task nobody stores can be garbage collected mid-flight and simply stop.
  Store it in a module-level set and discard on completion, or — better — do not fire and
  forget; use a `TaskGroup`.
- Async fixtures and tests need `pytest-asyncio` (or `anyio`) configured with an explicit
  mode. Without it the test function returns a coroutine that is never awaited, and pytest
  reports a pass.

## Dataclasses or Pydantic

Both make classes out of fields; they answer different questions, and using one where the
other belongs is a recurring source of either wasted CPU or missing validation.

| | `dataclass` | Pydantic `BaseModel` |
|---|---|---|
| Validates at runtime | no — annotations are not enforced | yes, and coerces per the field type |
| Cost per instance | close to a plain class | parsing and validation |
| Dependency | standard library | third party |
| Use for | internal value objects, config already validated, anything hot | HTTP bodies, queue messages, config files, any untrusted input |

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal
```

`frozen=True` makes the object hashable and safe to share; `slots=True` drops the instance
`__dict__`, which cuts memory and turns a typo'd attribute assignment into an
`AttributeError` instead of a silently ignored write; `kw_only=True` stops a later field
reorder from silently swapping two same-typed arguments at every call site.

The line to hold: validate once, at the boundary, with Pydantic, then convert to plain
dataclasses inside. Re-validating the same object at every layer buys nothing and costs on
every request — but do not invert it either, because a dataclass built straight from JSON
has annotations that are decoration and a `quantity` that may well be the string `"3"`.

## `pathlib` over `os.path`

```python
from pathlib import Path

config_dir = Path(__file__).resolve().parent / "config"
for template in sorted(config_dir.rglob("*.tmpl")):
    text = template.read_text(encoding="utf-8")
    template.with_suffix(".out").write_text(render(text), encoding="utf-8")
```

`Path` replaces a nest of `os.path.join`, `os.path.dirname`, `glob.glob` and `open` with one
object that knows how to compare, iterate, and reason about itself. `Path.mkdir(parents=True,
exist_ok=True)` removes the classic "check then create" race; `resolve()` before comparing
two paths, because `a/../b` and `b` are the same file and different strings.

**Always pass `encoding="utf-8"` explicitly.** Without it, `read_text` and `open` use the
platform's preferred encoding, which is UTF-8 on Linux and CI and historically something else
on Windows. The result is a file that reads correctly for everyone except one developer, or a
`UnicodeDecodeError` that appears only in the environment nobody can reproduce. Where a
library still demands a string, `str(path)` at that call site is fine — a narrow adapter, not
a reason to keep strings throughout.
