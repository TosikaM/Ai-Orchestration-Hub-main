# Python Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below, and so does a pattern already established in the package that you can
> cite with a `file:line`. A hub default that overrides a team's stated convention is a hub
> that gets uninstalled. Where this template and the repository disagree, follow the
> repository and name the rule you set aside.

`config/stack-mappings.json` maps this template to `django` and `fastapi`: snake_case
modules, Pydantic models as the mapping mechanism, `test_*.py` (or Django's `tests.py`) for
tests. Read `pyproject.toml` for `requires-python` before using syntax the project's floor
does not have, and say which version you read.

## Package layout

Use the `src/` layout. The single reason is worth more than it sounds: with `src/`, an
import of your package can only succeed if the package is actually installed, so the tests
exercise the thing you will ship rather than the working directory that happens to be on
`sys.path`. The classic failure it prevents is a package that passes CI and fails on
install because a data file or a subpackage was never declared.

```
src/orders/
  __init__.py          the public surface: a handful of re-exports, not everything
  models.py            Pydantic models at the boundary
  service.py           business logic, no framework imports
  repository.py        persistence, the only module that knows about the database
  errors.py
tests/
  test_service.py
  conftest.py
pyproject.toml
```

Keep `__init__.py` small. Anything it imports runs on first import of the package, so an
`__init__` that pulls in the database layer makes `import orders` open a connection — and
turns an unrelated unit test into an integration test. Where `__init__` re-exports, list
`__all__` explicitly so the public surface is a reviewable line in the diff.

Modules and functions are `snake_case`, classes are `PascalCase`, module-level constants
are `UPPER_SNAKE`. A leading underscore means private, and it is a real boundary in
practice: other modules importing `_helper` is a review comment, not a style preference.

## Typing conventions

Annotate every public function. Annotations that nothing checks decay into comments, so run
`mypy` or `pyright` in CI — the stack mapping already lists `pyright .` as a lint candidate
for FastAPI repos.

```python
from collections.abc import Iterable, Sequence
from typing import Protocol

def total_for(orders: Iterable[Order]) -> Decimal: ...
def page_of(orders: Sequence[Order], size: int = 20) -> list[Order]: ...
```

- **Accept the widest type you can use, return the narrowest you can promise.** Take
  `Iterable[Order]` when you only iterate; take `Sequence[Order]` when you index or need
  `len`. Return `list[Order]`, not `Iterable[Order]`, so the caller does not have to guess
  whether it can iterate twice.
- Use built-in generics (`list[str]`, `dict[str, int]`) and `X | None`; `typing.List` and
  `Optional[X]` are legacy spellings you will still meet in older files.
- `Protocol` over an abstract base class for a dependency you own the *use* of but not the
  implementation. The implementer needs no import of your package, which keeps the
  dependency arrow pointing the way you drew it.
- `Any` silently disables checking for everything downstream of it. Where it is genuinely
  needed, write a comment saying why; where the type is merely unknown, `object` forces the
  caller to narrow and is almost always what was meant.
- `TypedDict` for a dict shape crossing a boundary you do not control; a dataclass or model
  for anything you do.

## Pydantic models

Validate untrusted data once, at the boundary, and let the type system carry it from there.

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    customer_id: UUID
    quantity: int = Field(gt=0, le=100)
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None
```

- `extra="forbid"` is the setting that catches the renamed field. Pydantic's default is to
  drop unknown keys silently, so a client sending `customerID` gets a `422` with `forbid`
  and a mysteriously empty value without it.
- `frozen=True` on request and event models. A validated object that later gets mutated is
  no longer validated, and the mutation is usually three call frames from the bug report.
- Validate at the edge, not in the domain. Passing `CreateOrder` down to the repository
  couples persistence to the HTTP contract; convert to a domain object at the boundary and
  the two can change independently.
- Pydantic v1 spellings appear throughout older code: `.dict()` is now `model_dump()`,
  `.parse_obj()` is `model_validate()`, `@validator` is `@field_validator`, `Config` is
  `model_config`, and `BaseSettings` moved out to the separate `pydantic-settings` package.
  Check the pinned major version before writing either dialect — mixing them produces
  errors that name neither.

## Dependency injection

Pass collaborators in; do not reach out for them. A module that constructs its own database
client at import time cannot be tested without a database and cannot be reused with a
second configuration.

```python
class OrderService:
    def __init__(self, orders: OrderRepository, clock: Clock) -> None:
        self._orders = orders
        self._clock = clock
```

FastAPI has this built in, and the payoff is at test time rather than at write time:

```python
def get_order_service(session: Session = Depends(get_session)) -> OrderService:
    return OrderService(SqlOrderRepository(session), SystemClock())

@router.post("/orders")
async def create_order(body: CreateOrder, service: OrderService = Depends(get_order_service)):
    return await service.create(body.customer_id, body.quantity)

# tests/test_api.py
app.dependency_overrides[get_order_service] = lambda: OrderService(InMemoryOrders(), FrozenClock())
```

`dependency_overrides` replaces the provider for the whole app without patching imports,
which is why this is worth the indirection: `unittest.mock.patch` on a module path breaks
whenever the import is moved or aliased, and the breakage looks like a passing test that
silently exercises the real client. Clear the overrides in a fixture teardown, or the next
test file inherits them.

In Django the equivalent discipline is to keep business logic in plain functions and classes
that take their collaborators as arguments, and to let views and management commands do the
wiring. Module-level `Model.objects` calls at import time run before the app registry is
ready and fail with an error that names neither the module nor the cause.

## The mutable default argument

Default arguments are evaluated **once**, when the `def` statement executes — not on each
call. A mutable default is therefore shared state across every call in the process:

```python
def add_line(line: OrderLine, lines: list[OrderLine] = []) -> list[OrderLine]:
    lines.append(line)          # the same list, on every call, forever
    return lines

add_line(a)     # [a]
add_line(b)     # [a, b]   -- from a different request, in a different test
```

It survives review because it reads correctly and passes any test that calls the function
once. It surfaces as a request seeing another request's data, which is investigated as a
concurrency bug for a long time before anyone looks at the signature.

```python
def add_line(line: OrderLine, lines: list[OrderLine] | None = None) -> list[OrderLine]:
    lines = [] if lines is None else lines
    return [*lines, line]
```

The same trap has relatives worth knowing, because the rule is not identical in each:

- **Dataclasses** refuse it — a mutable default raises `ValueError` at class definition
  time, and you write `field(default_factory=list)`.
- **Pydantic models** copy the default per instance, so `items: list[str] = []` is actually
  safe there. Relying on that in a codebase that also has plain functions and dataclasses is
  how the rule gets misremembered; `Field(default_factory=list)` is the spelling that is
  correct everywhere.
- **Class attributes** have exactly the same shape: `class Cart: items = []` gives every
  instance the same list. Assign in `__init__`.

The general form is: any default that is evaluated once and can be mutated is shared. That
includes `datetime.now()` as a default — it freezes the value at import time, and the bug is
a timestamp that is always the moment the process started.
