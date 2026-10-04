# Angular Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below, and so does an established pattern you can point to in the existing
> source with a `file:line`. A hub default that overrides a team's stated convention is a
> hub that gets uninstalled. Where this template and the repository disagree, follow the
> repository and say out loud which rule you set aside.

This file loads only when the stack detector matched `angular`. It covers the conventions
that have held across Angular versions; the signal-era APIs are in `modern-patterns.md`.

## File and naming conventions

`config/stack-mappings.json` records this stack as `kebab-case.component.ts` files,
colocated `*.spec.ts` tests, and "NgRx or RxJS services" for state. Detect which of those
two the repo actually uses before writing either — introducing a second state mechanism
alongside an existing one is a decision, not a detail.

```
src/app/orders/
  order-list/
    order-list.component.ts      -> class OrderListComponent, selector app-order-list
    order-list.component.html
    order-list.component.spec.ts
  order.service.ts               -> class OrderService
```

The class name is the PascalCase of the file name plus its type suffix, and the selector
is the app prefix plus the kebab name. That threefold redundancy is what makes a symbol
findable from any one of the three: given only a selector in a template, you can locate
the file without an editor index — which matters because an agent grepping a repo does
not have one.

## Component shape

A component owns its template, its local UI state, and nothing else. Anything a second
component could plausibly need belongs in a service before the second component exists.

```typescript
@Component({
  selector: 'app-order-list',
  templateUrl: './order-list.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,   // not negotiable, see below
})
export class OrderListComponent {
  @Input({ required: true }) customerId!: string;
  @Output() readonly orderSelected = new EventEmitter<Order>();
}
```

- **`OnPush` from the first commit, never as a later optimization.** Retrofitting it onto
  a component that has been mutating its inputs in place means auditing every write, and
  the failure mode is a view that silently stops updating — no error, no stack trace, and
  a bug report that says "sometimes the total is wrong."
- **No method calls in templates except in event bindings.** `{{ computeTotal() }}` runs
  on every change-detection pass, which is far more often than the data changes. Compute
  the value when the input changes, or use a pure pipe.

Split containers from presentation: a routed container talks to services and passes plain
data down; the components below it take `@Input()`s, emit `@Output()`s, and inject nothing.
The payoff is testability — the presentational half needs no `TestBed` provider wiring.

## Services and the DI tree

Angular resolves a token by walking two trees: the element injector (the component's own
`providers`, then its ancestors') and then the environment injector chain (a lazily
loaded route's injector, then root). The first match wins, and a match one level down is
a *different instance*, not a shared one.

- `@Injectable({ providedIn: 'root' })` for stateless services and application-wide state,
  which gives one instance for the whole application. It is also
  tree-shakable: a service nobody injects never reaches the bundle.
- Component-level `providers: [...]` only when you genuinely want one instance per
  component instance, torn down with it. Per-wizard form state is the honest case.
- **The trap:** listing a `providedIn: 'root'` service again in a lazily loaded route's
  providers gives that route its own instance. Two copies of what everyone believes is
  one cache, and the divergence surfaces only on the second navigation into the feature.

## RxJS subscription lifecycle

Every manual `.subscribe()` is a resource you now own. An HTTP call that completes is
mostly harmless. A `Subject`, a router event stream, an interval, or a store selector
never completes, so a subscription to one keeps the component — and the entire view tree
it references — alive after destruction.

In order of preference: the `async` pipe, which subscribes on render and unsubscribes on
destroy and cannot forget; `takeUntilDestroyed()` where the version has it (see
`modern-patterns.md`); and finally the `destroy$` subject most existing code uses.

```typescript
private readonly destroy$ = new Subject<void>();

ngOnInit(): void {
  this.orders.changes$
    .pipe(switchMap(() => this.orders.load(this.customerId)), takeUntil(this.destroy$))
    .subscribe(orders => { this.orders = orders; this.cdr.markForCheck(); });
}

ngOnDestroy(): void { this.destroy$.next(); this.destroy$.complete(); }
```

`takeUntil` must be the **last** operator before `subscribe`. Placed earlier, a
`switchMap` downstream of it can keep its inner subscription open after the outer one is
torn down, which is a leak that looks exactly like correct code in review.

Never subscribe inside a subscribe. Choose the flattening operator by asking what should
happen when a second value arrives while the first is still in flight:

| Operator | Behaviour on overlap | Typical use |
|---|---|---|
| `switchMap` | cancels the in-flight inner | typeahead, reload on route change |
| `concatMap` | queues, preserves order | writes that must not reorder |
| `mergeMap` | runs both | independent parallel fetches |
| `exhaustMap` | ignores the new one | submit buttons, double-click protection |

`shareReplay(1)` has one sharp edge worth remembering: with the default `refCount: false`
it keeps its source subscription alive after the last subscriber leaves, which for an
HTTP-backed stream is a cached response nobody can invalidate and for an interval is a
timer that never stops. Write `shareReplay({ bufferSize: 1, refCount: true })` unless you
specifically want the cache to outlive its consumers.

## Change detection

With `OnPush`, Angular re-checks a component when an `@Input()` reference changes, when an
event fires inside it, when an `async` pipe in its template emits, or when something calls
`markForCheck()`. Mutating an array or object in place changes none of those, so the view
does not update:

```typescript
this.items.push(item);              // OnPush will not notice
this.items = [...this.items, item]; // new reference — it will
```

When state arrives from outside Angular's zone (a WebSocket callback, a third-party
widget, a `setTimeout` in a library), inject `ChangeDetectorRef` and call `markForCheck()`
after the assignment. Reach for `detectChanges()` only when you know you need a synchronous
pass right now, and never call it from `ngOnDestroy` — the view is already gone.
`trackBy` on every `*ngFor` over a list that changes: without it Angular destroys and
recreates every DOM node on each emission, which also resets focus and scroll position.

## Reactive forms

Reactive forms over template-driven ones for anything with validation, because the shape
lives in TypeScript where it can be typed, unit tested, and read without opening the HTML.

```typescript
private readonly fb = inject(FormBuilder);

readonly form = this.fb.nonNullable.group({
  email: ['', [Validators.required, Validators.email]],
  quantity: [1, [Validators.required, Validators.min(1)]],
  notes: [''],
}, { validators: [quantityWithinCreditLimit] });
```

- `nonNullable` matters more than it looks: without it every control's type is `T | null`
  because `reset()` sets controls back to `null`, and the `| null` then leaks into every
  consumer of `form.value`.
- Cross-field rules belong on the group, not on a control. A validator on `quantity` that
  reads `this.form.get('creditLimit')` runs before the sibling exists during construction.
- `form.value` omits disabled controls; `form.getRawValue()` includes them. Submitting
  `value` from a form with a disabled field is the standard way a required field reaches
  the API as `undefined`.
- `setValue` requires every control and throws when one is missing, which is what you want
  on a full load; `patchValue` accepts a subset and silently ignores unknown keys, which is
  what you want for a partial update and is also how a typo becomes a no-op.
- For expensive validation use `{ updateOn: 'blur' }` rather than debouncing inside an
  async validator.

## Testing

Tests are `*.spec.ts` beside the file they cover, run with `npm test` or `ng test` per the
stack mapping. Assert on rendered output through `fixture.debugElement`, not on component
fields — a test that only reads fields passes even when the template binding is misspelled.

## Anti-patterns

- Business logic in a component, so it can only be tested through a fixture.
- `subscribe()` inside `subscribe()`, which makes cancellation impossible to reason about.
- Manual subscription with no teardown path in `ngOnDestroy`.
- `any` on an HTTP response, which discards the one place the API contract was checkable.
- A shared service with public mutable fields instead of an observable or a signal, so no
  consumer can be notified of a change.
