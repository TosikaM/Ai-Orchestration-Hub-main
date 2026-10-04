# .NET — Modern Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below. So does the `<TargetFramework>` in the `.csproj`: several features here
> arrived in a specific release, and proposing an API the project cannot compile wastes a
> round trip. Read the target framework and the `LangVersion` first, and say which you read.

Rough availability: records from C# 9, `required` members in C# 11, primary constructors and
collection expressions in C# 12, `TimeProvider`, keyed DI and `ConfigureAwaitOptions` in
.NET 8, and the built-in `Microsoft.Extensions.Http.Resilience` handler from .NET 8.
Minimal APIs have gained capability in every release since .NET 6, so check the release
notes rather than assuming a limit you remember still holds.

That list is a floor, not a ceiling, and it is **recorded rather than measured**: .NET ships
a major every November. Read `<TargetFramework>` and `<LangVersion>` from the `.csproj`, say
which you read, and treat anything past this list as available-but-unverified rather than
absent.

> **New solution?** This file assumes .NET code you are fitting in with. When there is
> none, the floor is `dotnet-service` or `dotnet-library` in
> `config/architecture-baseline.json` — prescriptive for new work, naming the target
> runtime, the vertical-slice modular-monolith default, the fourteen production-grade
> concerns, and the dependencies not to take (MediatR, AutoMapper and FluentAssertions all
> changed licence).

## The options pattern

Configuration should be bound once, validated once, and injected as a typed object. Reading
`IConfiguration["Some:Key"]` deep inside a service is how a typo becomes `null` at three in
the morning instead of an error at startup.

```csharp
public sealed class OrderApiOptions
{
    public const string SectionName = "OrderApi";

    [Required, Url]      public required string BaseUrl { get; init; }
    [Range(1, 300)]      public int TimeoutSeconds { get; init; } = 30;
}

builder.Services
    .AddOptions<OrderApiOptions>()
    .BindConfiguration(OrderApiOptions.SectionName)
    .ValidateDataAnnotations()
    .Validate(o => !o.BaseUrl.EndsWith('/'), "BaseUrl must not have a trailing slash")
    .ValidateOnStart();
```

`ValidateOnStart()` is the line that earns the pattern. Without it validation is lazy: the
first request to touch the options throws, so a misconfigured deployment passes its health
check, goes live, and fails for users rather than for the pipeline. With it the process
refuses to start, which is the failure you want.

Pick the accessor by lifetime, and the choice is not cosmetic:

| Accessor | Lifetime | Use when |
|---|---|---|
| `IOptions<T>` | singleton, computed once | the value cannot change while the process runs |
| `IOptionsSnapshot<T>` | scoped, recomputed per scope | a request should see reloaded configuration |
| `IOptionsMonitor<T>` | singleton with change notification | a singleton or background service needs current values |

Injecting `IOptionsSnapshot<T>` into a singleton is a compile-time success and a runtime
`InvalidOperationException` about a scoped service in a root provider — one of the few DI
mistakes .NET catches for you, and only because scope validation is on by default in
development. Keep it on in every environment.

## Nullable reference types

```xml
<Nullable>enable</Nullable>
<WarningsAsErrors>nullable</WarningsAsErrors>
```

Enable it for the whole project rather than per file, and promote the warnings to errors —
a nullable warning that only appears in a build log nobody reads provides no safety at all.
In a large legacy project turn it on project by project, starting with the domain layer,
because that is where a `null` costs the most and where the annotation density is lowest.

Treat the null-forgiving `!` as a claim you are making without evidence. Each one is worth a
comment saying why it is true, and most of them are better rewritten:

```csharp
var order = await orders.GetAsync(id, ct);
if (order is null) return Result.NotFound($"Order {id}");   // instead of order!.Total
```

`required` moves the same guarantee to construction time, so the type system enforces it
rather than a constructor overload nobody uses:

```csharp
public sealed class OrderDto
{
    public required Guid Id { get; init; }
    public required string Reference { get; init; }
    public string? CancellationReason { get; init; }   // genuinely optional, and it says so
}
```

Since .NET 8, `System.Text.Json` honours `required` on deserialization and throws when the
JSON omits the member, which turns a silently half-populated DTO into a request-level error.

## Records and value semantics

Records for anything that is data: commands, queries, DTOs, value objects, configuration
snapshots. Classes for anything with identity or behaviour.

```csharp
public sealed record Money(decimal Amount, string Currency)
{
    public Money Add(Money other) => Currency == other.Currency
        ? this with { Amount = Amount + other.Amount }
        : throw new InvalidOperationException("Currency mismatch");
}
```

Two edges to keep in mind. Record equality is member-wise, which means a record containing a
`List<T>` compares that list **by reference** — two records with equal contents are not
equal, and a dictionary keyed on such a record misses. Use an immutable collection with
value equality, or override `Equals`. And a `record struct` is mutable unless declared
`readonly record struct`, which reintroduces the defensive-copy surprises structs are known
for.

Primary constructors on non-record classes (C# 12) capture parameters as fields rather than
generating properties. They are excellent for dependency injection, as in the handler in
`dotnet-patterns.md`, and misleading as a data carrier — no equality, no deconstruction,
and the parameter stays mutable inside the class.

## Async: the rules that actually bite

- **Async all the way.** `.Result` and `.Wait()` deadlock wherever a synchronization context
  exists and starve the thread pool everywhere else. The symptom is a service that is fine
  under test and hangs under load, which is the most expensive shape of bug there is.
- **`async void` only for event handlers.** Anywhere else the exception is raised on the
  thread pool, unobserved by the caller, and the process may terminate. Return `Task`.
- **Flow `CancellationToken` everywhere,** including into library calls. In ASP.NET Core the
  request's token is available as an action parameter or via `HttpContext.RequestAborted`.
- **`ValueTask` only for a hot path that usually completes synchronously,** and only when
  the result is awaited exactly once. Awaiting a `ValueTask` twice is undefined behaviour
  rather than an exception, so the cost of getting it wrong is a wrong answer.
- **`Task.WhenAll` for independent work,** but capture the tasks first: starting five and
  awaiting each in turn is a sequential loop wearing async syntax.
- **`TimeProvider` instead of `DateTime.UtcNow`** (.NET 8) wherever time is a business input.
  It makes "expires after 30 days" testable without waiting or reaching into statics.

### `ConfigureAwait`

In a **library**, write `ConfigureAwait(false)` on every await. You do not know what context
the caller has, and resuming on a UI thread you did not ask for is a deadlock or a
performance cliff you cannot reproduce.

In an **ASP.NET Core application** it is a genuine no-op: there is no synchronization
context to capture, so adding it changes nothing at runtime. Say that plainly rather than
adding the call as ritual — but if the repository has a rule requiring it, follow the
repository.

## `IAsyncEnumerable<T>`

Stream when the result set is large or unbounded, so memory does not scale with the row
count and the first row reaches the consumer before the last is read.

```csharp
public async IAsyncEnumerable<OrderDto> StreamAsync(
    Guid customerId, [EnumeratorCancellation] CancellationToken ct = default)
{
    var query = db.Orders.Where(o => o.CustomerId == customerId).AsNoTracking();
    await foreach (var order in query.AsAsyncEnumerable().WithCancellation(ct))
        yield return OrderDto.FromDomain(order);
}
```

`[EnumeratorCancellation]` is what lets a caller's `WithCancellation(token)` reach your
token parameter; without it the parameter is silently ignored and the stream cannot be
cancelled. The other trap is lifetime: the query runs while the consumer enumerates, so
returning an `IAsyncEnumerable` backed by a scoped `DbContext` from a method whose scope
ends on return gives an `ObjectDisposedException` at the consumer, far from the cause.
Enumerate inside the scope, or hand back a materialized list and accept the memory.

## Minimal APIs

```csharp
var orders = app.MapGroup("/api/orders").RequireAuthorization().WithTags("Orders");

orders.MapGet("/{id:guid}", async Task<Results<Ok<OrderDto>, NotFound>> (
        Guid id, ISender sender, CancellationToken ct) =>
    await sender.Send(new GetOrderQuery(id), ct) is { } dto
        ? TypedResults.Ok(dto)
        : TypedResults.NotFound());
```

`MapGroup` applies the prefix, auth, and filters once for the whole group instead of
repeating them per endpoint, where one omission is a public endpoint nobody notices.
`TypedResults` with an explicit `Results<,>` return type gives you compile-time checking
that the handler returns only the statuses it documents, and OpenAPI generation gets those
statuses for free rather than from hand-written attributes that drift.

Prefer controllers when the repository already uses them, when model binding gets complex,
or when the team relies on filters and conventions that minimal APIs express differently.
Mixing both in one project is supported and is usually the right migration path; mixing
both in one *feature* is not.
