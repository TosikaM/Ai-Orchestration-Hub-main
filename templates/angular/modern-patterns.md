# Angular — Modern Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below. So does the version floor in `package.json`: half of what follows does
> not exist in older Angular releases, and proposing an API the project cannot compile is
> worse than proposing nothing. Read `@angular/core` in `package.json` first and say which
> version you read.

Rough availability, so you can check before you write:

| Feature | Arrived in |
|---|---|
| `inject()`, `takeUntilDestroyed()` | 14 / 16 |
| `signal()`, `computed()`, `effect()` | 16 |
| Built-in control flow (`@if`, `@for`), `@defer` | 17 |
| Signal `input()`, `output()`, `model()`, signal queries | 17.1 – 17.2 |
| Standalone by default, `linkedSignal()`, `resource()` (experimental) | 19 |
| Zoneless change detection stabilising, `httpResource()` | 19 – 20 |

That table is a floor, not a ceiling, and it is **recorded rather than measured** — Angular
ships two majors a year, so it goes stale faster than anything else in this directory. Read
`@angular/core` in `package.json`, say which version you actually read, and treat anything
newer than the last row as available-but-unverified rather than absent.

> **New application?** This file describes how to write modern Angular inside a project
> that already exists. When there is none, the floor is the `angular` entry in
> `config/architecture-baseline.json` — prescriptive for new work, and it names the target
> version, the standalone-plus-signals default, the fourteen production-grade concerns,
> and the dependencies not to take.

## Standalone components

From v19 a component is standalone unless it says `standalone: false`; before that it
needed `standalone: true`. Either way the shape is the same, and the win is that a
component declares its own dependencies instead of inheriting whatever its `NgModule`
happened to import.

```typescript
@Component({
  selector: 'app-order-list',
  imports: [RouterLink, OrderCardComponent, CurrencyPipe],   // the whole dependency list
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `...`,
})
export class OrderListComponent {}
```

Bootstrap and configure at the application root with providers instead of module imports:

```typescript
bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimationsAsync(),
  ],
});
```

`withComponentInputBinding()` binds route params and query params straight to matching
`@Input()`/`input()` names, which removes a whole category of `ActivatedRoute` subscription
code — and with it the leaks that code used to cause.

In a repo that still has `NgModule`s, migrate a feature at a time; a half-migrated feature
where a standalone component is still declared in a module fails at build with a message
that does not name the cause. The official schematics (`ng generate @angular/core:standalone`,
`:control-flow`, `:signal-inputs`) do the mechanical part — run one, then read the diff.

## `inject()`

`inject()` reads from the current injection context and returns the token, so a dependency
becomes a field initializer — `private readonly orders = inject(OrderService);` — rather
than a constructor parameter. It works in field initializers, in factory functions, and in
plain functions called from either.

Beyond the shorter constructor it enables something a constructor cannot: reusable
functions that resolve their own dependencies — an `injectPageParam(name)` helper that
injects `ActivatedRoute` internally can be shared by every routed component without any of
them declaring the route in a constructor.

**The one failure mode:** calling `inject()` outside an injection context throws `NG0203`.
Field initializers, constructors, and provider factories are inside; a callback that runs
later — inside `subscribe`, `setTimeout`, or a promise continuation — is not. When you need
it later, capture the injector or the value at construction time, or wrap the call in
`runInInjectionContext(injector, () => ...)`.

## Signals

A signal is a value plus a dependency graph. Read it by calling it; write with `set` or
`update`. Derived state is `computed()` — lazy, memoized, and it recomputes only when a
dependency it actually read has changed.

```typescript
readonly query    = signal('');
readonly orders   = signal<Order[]>([]);
readonly filtered = computed(() =>
  this.orders().filter(o => o.ref.includes(this.query())));
```

Component inputs and outputs have signal forms, which also fixes the "input is `undefined`
during the constructor" problem because a `computed` simply does not run until read:

```typescript
readonly customerId = input.required<string>();
readonly pageSize   = input(20, { transform: numberAttribute });
readonly selected   = output<Order>();
readonly value      = model<string>('');    // two-way: [(value)]
readonly grid       = viewChild.required(GridComponent);
```

The rule that keeps signal code sane: **derive with `computed`, react with `effect`, and
never use `effect` to copy one signal into another.** An effect that writes state builds a
graph the framework cannot order for you, and the symptom is a value that is correct one
render late. Effects belong at the edges — logging, persisting to `localStorage`, calling
into a non-Angular library, syncing the document title. `linkedSignal()` covers the common
legitimate case of writable state that resets when a source changes.

`untracked(() => ...)` reads a signal without subscribing to it, which is how you use a
value inside an effect without re-running on its every change.

## Interop with RxJS

`toSignal(source$, { initialValue })` subscribes immediately and unsubscribes when the
injection context is destroyed; `toObservable(sig)` goes the other way. `toSignal` needs an
`initialValue` unless the source emits synchronously (`requireSync: true`, which throws at
runtime if it does not). Streams still win wherever the question is about time — debouncing,
retry with backoff, cancellation — so convert at the boundary rather than picking a side.

## `takeUntilDestroyed()`

```typescript
constructor() {
  this.socket.messages$.pipe(takeUntilDestroyed())
    .subscribe(msg => this.messages.update(list => [...list, msg]));
}
```

Called with no argument it must run in an injection context, where it finds the
`DestroyRef` itself. Outside one — in `ngOnInit`, or in a method — inject the `DestroyRef`
as a field and pass it explicitly: `takeUntilDestroyed(this.destroyRef)`. That is the
whole API, and it replaces the `destroy$` subject boilerplate wholesale.

## `resource()` — async state without a subscription

`resource()` (and `rxResource()` for observable loaders) turns a request signal plus a
loader into signals for value, status and error, and re-runs the loader when the request
changes, aborting the previous call.

```typescript
readonly orders = resource({
  params: () => ({ customerId: this.customerId() }),
  loader: ({ params, abortSignal }) =>
    fetch(`/api/customers/${params.customerId}/orders`, { signal: abortSignal })
      .then(r => r.json() as Promise<Order[]>),
});
// template: @if (orders.isLoading()) { ... } @else { ... orders.value() }
```

Be honest about its status: the API has changed shape across releases (the request field
was renamed, and `httpResource` landed later), so confirm the signature against the
installed version instead of trusting this snippet. For anything requiring retry policy,
polling, or shared caching, an RxJS service or a data library is still the better answer.

## Routing: `canMatch` over `canActivate`

Functional guards are plain functions that can `inject()`:

```typescript
export const canMatchAdmin: CanMatchFn = () =>
  inject(AuthService).isAdmin() || inject(Router).createUrlTree(['/forbidden']);

export const routes: Routes = [
  { path: 'admin', canMatch: [canMatchAdmin],
    loadChildren: () => import('./admin/routes').then(m => m.ADMIN_ROUTES) },
  { path: 'admin', component: UpgradePromptComponent },
];
```

`canMatch` runs *during* route matching, so a rejection means the route never matched:
the lazy chunk is never downloaded, and the router falls through to the next route that
does match — which is what makes the two-entry pattern above possible. `canActivate` runs
after the route has been matched and the chunk fetched, so it can only redirect. Use
`canMatch` for "this user should not have this feature at all" and `canActivate` for
"this user needs to do something first."

## Control flow and `@defer`

```html
@if (orders.value(); as list) {
  @for (order of list; track order.id) {
    <app-order-card [order]="order" />
  } @empty { <p>No orders yet.</p> }
} @else { <app-spinner /> }

@defer (on viewport; prefetch on idle) {
  <app-order-chart [orders]="orders.value()" />
} @placeholder { <div class="chart-skeleton"></div> }
```

`track` is required on `@for` and is not decoration — it is what makes the diff stable, and
getting it wrong (tracking `$index` over a reordering list) re-renders rows and loses focus
and scroll state. `@defer` moves a component and its transitive imports into a separate
chunk fetched on the stated trigger; it only helps if the deferred component is not also
imported eagerly somewhere else in the same template.
