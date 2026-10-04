# Node.js — Modern Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below. So does `engines.node` in `package.json`: nearly everything here has a
> version floor, and suggesting an API the deployed runtime does not have is worse than
> suggesting nothing. Read the floor first and say which version you read.

Rough availability: `node:` prefix always; `AbortSignal.timeout` from 17.3; `--env-file`
from 20.6; the test runner stable from 20; `import.meta.dirname` from 20.11; import
attributes with `with` from 20.10; `AbortSignal.any` from 20.3; `require()` of synchronous
ESM from 22.12, backported into 20.19. Flags around coverage and the permission model have
been renamed between releases — check `node --help` on the pinned version rather than
trusting a snippet, including this one.

## ESM as the default

New packages should be `"type": "module"`. Beyond alignment with the rest of the ecosystem,
ESM is what makes static analysis — tree shaking, unused-export detection, the `exports`
encapsulation boundary — possible at all, because the import graph is knowable without
executing the code.

```ts
import { readFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";
import config from "./config.json" with { type: "json" };

const templateDir = path.join(import.meta.dirname, "templates");
```

Import attributes (`with { type: "json" }`) are mandatory for JSON in ESM — a plain import
throws. The older `assert { type: "json" }` spelling is deprecated; if you meet it in an
existing file, that file predates Node 20.10 or was written against it.

## The `node:` prefix

Write `node:fs`, not `fs`, for every builtin. Three reasons, in increasing order of
importance: it reads unambiguously as a builtin rather than a dependency; some newer
builtins (`node:test`, `node:sea`) are *only* resolvable with the prefix; and it removes an
attack surface, because a package named `fs` or `path` installed into `node_modules` — by
typosquat or by dependency confusion — cannot shadow a prefixed specifier. The
`unicorn/prefer-node-protocol` lint rule enforces this in one line.

## The native test runner

For a Node service with no DOM and no heavy transform step, `node:test` removes an entire
dependency tree and its configuration surface. Be honest about where it does not fit:
browser-environment tests, JSX, and rich snapshot workflows are still Vitest or Jest
territory, and a repo already invested in one of those has no reason to switch.

```ts
import { describe, it, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createOrder } from "./order.service.js";

describe("createOrder", () => {
  let repository;
  beforeEach(() => { repository = { save: mock.fn(async o => o) }; });

  it("persists the order and returns its id", async () => {
    const order = await createOrder({ customerId: "c-1", lines: [] }, repository);
    assert.equal(repository.save.mock.callCount(), 1);
    assert.match(order.id, /^ord_/);
  });

  it("rejects an empty customer id", async () => {
    await assert.rejects(
      () => createOrder({ customerId: "", lines: [] }, repository),
      /customerId/,
    );
  });
});
```

Always import `node:assert/strict`, not `node:assert`. The default export's `equal` uses
loose comparison, so `assert.equal(1, "1")` passes — a green test asserting the wrong thing
is worse than no test. Run with `node --test`, add `--watch` while developing,
`--test-name-pattern` to focus, and `mock.timers` when a test would otherwise wait on real
time. Because `mock.fn` and friends are scoped to the runner, there is no global mock state
to reset between files.

## Structured logging

Log JSON objects, one per line, to stdout, and let the platform handle routing. A
human-formatted string is convenient locally and useless the first time you need every
failure for one order id across three services.

```ts
import pino from "pino";
import { AsyncLocalStorage } from "node:async_hooks";

export const requestContext = new AsyncLocalStorage<{ requestId: string }>();

export const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  redact: ["req.headers.authorization", "*.password", "*.token"],
  mixin: () => requestContext.getStore() ?? {},
});

// at the edge
app.use((req, res, next) =>
  requestContext.run({ requestId: req.header("x-request-id") ?? randomUUID() }, next));

// anywhere below, with no plumbing
logger.info({ orderId, lineCount }, "order created");
```

`AsyncLocalStorage` carries the correlation id across every await in the request without
threading a context parameter through every signature — which is the only reason correlation
ids survive contact with a real codebase. Three habits go with it: put data in the object
and keep the message a stable string, so logs are queryable; configure `redact` before the
first secret is logged rather than after; and never log inside a library — return or throw
and let the application decide.

## `AbortSignal`

`AbortSignal` is the runtime's one cancellation vocabulary, and it composes: `fetch`,
`fs/promises`, `timers/promises`, `events.once`, streams and readline all accept one, so a
single signal can tear down a whole operation.

```ts
import { setTimeout as delay } from "node:timers/promises";

export async function fetchOrder(id: string, signal?: AbortSignal) {
  const timeout = AbortSignal.timeout(5_000);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  const response = await fetch(`${config.API_URL}/orders/${id}`, { signal: combined });
  if (!response.ok) throw new AppError(`Upstream ${response.status}`, "UPSTREAM", 502);
  return response.json();
}
```

- `AbortSignal.timeout(ms)` beats a hand-rolled `setTimeout` plus `controller.abort()`
  because it does not keep the event loop alive and there is no timer left to clear.
- `AbortSignal.any([...])` is how "the caller cancelled" and "we timed out" become one
  signal without either side knowing about the other.
- Accept an optional `signal` on any function that performs I/O, and pass it down. A
  function that ignores the signal it was given is the reason a shutdown hangs for thirty
  seconds.
- In your own loops check `signal.aborted` between iterations and throw
  `signal.reason ?? new Error("Aborted")`; a cancelled operation that keeps running silently
  is indistinguishable from a slow one.
- An abort surfaces as an `AbortError` (`err.name === "AbortError"`, or `TimeoutError` for
  a timeout signal). Do not report it as a server error — nothing failed; someone left.

## Top-level await

Top-level await works only in ESM, and it changes the module's contract: importing it
becomes asynchronous for every importer up the graph, and `require()` of that module fails
even on the Node versions that can otherwise require ESM. That makes it excellent for the
one thing at the top of the process and a poor choice everywhere else.

```ts
// config.ts — a good use: the process cannot usefully continue without this
export const secrets = await loadSecretsFromVault();
```

Good: loading configuration or secrets, opening the connection the whole process needs,
choosing an implementation with `await import()`. Bad: anything on the import path of a
library other people consume, and anything that could be a function the caller awaits when
it actually needs the value.

## Small conveniences worth knowing

- `node --env-file=.env` loads environment variables without `dotenv`. It does not expand
  variables or run any code, which is a feature; add `--env-file-if-exists` where the file
  is optional.
- `node --watch src/server.ts` restarts on change with no `nodemon`.
- `structuredClone(value)` is a global deep clone that handles `Map`, `Set`, `Date` and
  cycles, so `JSON.parse(JSON.stringify(x))` has no remaining excuse — that idiom silently
  drops `undefined`, functions, and every `Date` becomes a string.
- `fetch`, `FormData`, `Headers` and `WebStream` are globals. Reach for a client library
  when you need retries, connection pooling policy, or interceptors, not for the request
  itself.
- The permission model (`node --permission`) is still moving between releases; treat it as
  defence in depth to evaluate, not as a boundary to rely on today.
