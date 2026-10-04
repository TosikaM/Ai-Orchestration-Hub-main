# Node.js / TypeScript Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below, and so does a pattern already established in `src/` that you can cite
> with a `file:line`. A hub default that overrides a team's stated convention is a hub that
> gets uninstalled. Where this template and the repository disagree, follow the repository
> and say which rule you set aside.

`config/stack-mappings.json` maps this template to `node-typescript`, `react`, `nextjs`,
`vue` and `svelte`, so it deliberately covers what those have in common — module layout,
errors, configuration, dependency boundaries, and the ESM/CJS seam. Component conventions
belong to the framework and to the repo's own docs, not here. Check `package.json` for the
runtime floor in `engines` and for `"type"` before writing any import.

## Module layout

Organize by feature, not by technical role. `src/orders/` containing its handler, service,
repository, and types is one thing to read, move, or delete; `controllers/`, `services/`
and `models/` spreads every feature across three directories and every change across three
diffs.

```
src/
  orders/
    index.ts            the only file other features may import from
    order.service.ts
    order.repository.ts
    order.types.ts
    order.service.test.ts
  shared/
    result.ts
    logger.ts
  config.ts             parsed once, at startup
  server.ts             wiring only
```

`index.ts` is a deliberate export surface, not a barrel over everything. Re-export the two
or three symbols other features legitimately need, and let the rest stay private. A barrel
that re-exports `*` from every file in the directory defeats the boundary and, in bundled
apps, drags the whole feature into anything that imports one function from it.

## Dependency boundaries

State the direction and then enforce it mechanically, because a boundary that lives only in
a README is a boundary that is already broken somewhere nobody has looked.

- Domain and service code must not import the web framework, the ORM, or the SDK of any
  vendor. Pass in what it needs; keep the adapters at the edge.
- Features import each other only through `index.ts`. Deep imports into a sibling's
  internals make that sibling impossible to refactor.
- `shared/` may not import from a feature. The moment it does, it is a feature.

```jsonc
// eslint.config.js — the rule that makes the above real
"import/no-restricted-paths": ["error", { zones: [
  { target: "./src/orders/domain", from: "./src/orders/http" },
  { target: "./src/shared",        from: "./src/orders" },
]}]
```

Circular imports deserve a specific warning: they usually still "work", right up until
module initialization order changes and one side observes `undefined` for something it
imported at the top level. The error message names a property access, not the cycle. Run
`madge --circular src/` or the equivalent lint rule in CI rather than diagnosing that later.

## Error handling

Distinguish the two kinds of failure, because they want opposite responses. An **operational
error** is an expected outcome of a valid request — the record is missing, the upstream
returned 503, the input failed validation — and the caller should handle it. A **programmer
error** is a bug; the honest response is to let it crash and let the supervisor restart.

```ts
export class AppError extends Error {
  constructor(message: string, readonly code: string, readonly status: number,
              options?: { cause?: unknown }) {
    super(message, options);
    this.name = new.target.name;
  }
}

export class OrderNotFoundError extends AppError {
  constructor(id: string, cause?: unknown) {
    super(`Order ${id} not found`, "ORDER_NOT_FOUND", 404, { cause });
  }
}
```

- Always attach `cause` when re-throwing. Without it the original stack — the one naming the
  socket timeout or the constraint violation — is gone, and the log says only that something
  failed in the handler.
- Never throw a string or a plain object. `catch (e)` is typed `unknown` in TypeScript for
  exactly this reason; narrow with `e instanceof AppError` and have a final branch that
  handles a non-`Error` throw rather than assuming `e.message` exists.
- Catch to *add information or make a decision*. A `try/catch` that logs and rethrows
  produces the same failure logged five times at five levels, which makes an incident harder
  to read, not easier.
- One error translator at the edge — Express error middleware, a route wrapper, a top-level
  handler — maps error codes to responses. Handlers throw; only the edge formats.
- An unhandled promise rejection terminates the process by default in modern Node. That is
  the correct default; do not install a handler that swallows it to keep the service up,
  because the process then continues from an unknown state. Log it and exit.
- Floating promises are the way this most often happens. Turn on
  `@typescript-eslint/no-floating-promises` — every call must be awaited, returned, or
  explicitly marked `void`.

## Configuration

Parse the environment exactly once, at startup, into a frozen typed object, and fail loudly
when it is wrong.

```ts
import { z } from "zod";

const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().url(),
});

const parsed = schema.safeParse(process.env);
if (!parsed.success) {
  console.error("Invalid configuration:", z.treeifyError(parsed.error));
  process.exit(1);
}

export const config = Object.freeze(parsed.data);
```

Reading `process.env.SOMETHING` in the middle of a module defeats all of this: the value is
`string | undefined` at every use site, a typo yields `undefined` rather than an error, and
the module becomes untestable without mutating global state. One module reads `process.env`;
everything else imports `config`.

Never log the parsed config, and never include a secret in an error message. If you need to
prove what was loaded, log the *keys* and whether each was present.

## The ESM/CJS boundary

This is where most Node build problems actually live, so establish the facts before
proposing a fix.

- `"type": "module"` in `package.json` makes every `.js` file in the package ESM. `.mjs` and
  `.cjs` are explicit and win over the field, which makes them useful for the odd file that
  must be the other kind.
- In ESM, relative specifiers need their file extension: `import "./order.service.js"` —
  and in a TypeScript project compiled to ESM that means writing `.js` in a `.ts` file,
  which looks wrong and is correct. `"moduleResolution": "NodeNext"` in `tsconfig.json` is
  what makes TypeScript check this instead of letting it fail at runtime.
- ESM has no `__dirname`, `__filename`, or `require`. Use `import.meta.dirname` (Node 20.11
  and later) or `fileURLToPath(import.meta.url)`, and `createRequire(import.meta.url)` for
  the rare package with no ESM entry point.
- ESM can import CJS. The `module.exports` object arrives as the default export; named
  exports are recovered by static analysis of the CJS source, which fails for exports built
  dynamically. When a named import from a CJS package is `undefined`, import the default and
  destructure from it.
- CJS could not `require()` an ESM module for years. Recent Node versions (22.12 and later,
  backported into 20.19) allow it when the target graph has no top-level await; a graph with
  top-level await still throws. Confirm against the version in `engines` before relying on
  it, and prefer `await import()` in code that must work on the older floor.
- Publishing both formats invites the **dual package hazard**: a consumer that resolves both
  copies gets two module instances, so `instanceof` fails and module-level state exists
  twice. Ship one format when you can; when you cannot, keep all state and classes in a
  single CJS core that both entry points re-export.

```jsonc
// package.json — the export surface, stated once
{
  "type": "module",
  "engines": { "node": ">=20.19" },
  "exports": {
    ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" },
    "./package.json": "./package.json"
  },
  "files": ["dist"]
}
```

The `exports` map is also an encapsulation boundary: paths it does not list cannot be
imported by consumers at all, which stops a downstream repo from depending on your internal
file layout and then breaking when you rename it.
