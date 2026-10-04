# .NET Patterns

> **Precedence.** This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks
> every rule below, and so does a pattern already established in the solution that you can
> cite with a `file:line`. A hub default that overrides a team's stated convention is a hub
> that gets uninstalled. When this template and the repository disagree, follow the
> repository and name the rule you set aside.

This file loads when the detector matched `dotnet-cqrs`, `dotnet-query`, or
`dotnet-shared-lib`. `config/stack-mappings.json` records the conventions it expects to
find — confirm each one against the solution before relying on it, because the detector
matched a file pattern, not a design.

> **New solution?** This file describes how to fit in with .NET code that already exists.
> When there is none, the floor is `config/architecture-baseline.json` (`dotnet-service`
> or `dotnet-library`), which is prescriptive for new work and names the target runtime,
> the required cross-cutting concerns, and the dependencies not to take. Read it first;
> the rest of this file still applies to the code you then write.

## Handler shape

One command, one handler, one transaction. The command is a `record` so equality and
`with` come free and nobody adds behaviour to it later.

```csharp
public sealed record CreateOrderCommand(Guid CustomerId, IReadOnlyList<OrderLine> Lines)
    : ICommand<Result<Guid>>;

public sealed class CreateOrderCommandHandler(
    IOrderRepository orders,
    IUnitOfWork unitOfWork,
    ILogger<CreateOrderCommandHandler> logger)
    : ICommandHandler<CreateOrderCommand, Result<Guid>>
{
    public async Task<Result<Guid>> Handle(CreateOrderCommand command, CancellationToken ct)
    {
        var order = Order.Create(command.CustomerId, command.Lines);
        await orders.AddAsync(order, ct);
        await unitOfWork.SaveChangesAsync(ct);
        logger.LogInformation("Created order {OrderId}", order.Id);
        return Result.Success(order.Id);
    }
}
```

`ICommand<T>` / `ICommandHandler<,>` above are the **dispatcher-agnostic** names. In a
solution already on MediatR they are `IRequest<T>` and `IRequestHandler<,>` — follow the
solution. For a **new** solution, `config/architecture-baseline.json` forbids taking
MediatR: it has been commercially licensed since v12, and the in-process dispatch a
vertical-slice codebase needs is roughly forty lines — an interface, a DI assembly scan,
and a thin sender that resolves and invokes. The shape below is identical either way; only
the interface names and who owns them change.

Four rules behind that shape:

- **A handler never sends another command.** Chaining handlers through `ISender` hides the
  transaction boundary: the inner handler may commit, the outer one may then fail, and the
  system is left half-written with no single place to read the sequence. Extract the shared
  work into a domain service and call it from both handlers.
- **Validation lives in a pipeline behaviour, not in `Handle`.** A `ValidationBehavior<,>`
  registered once runs FluentValidation for every request and returns the failure before the
  handler starts, so no handler has to remember to check and none of them drift.
- **Expected failure is a return value; unexpected failure is an exception.** "Customer not
  found" is a `Result` — it is a normal outcome of a valid request. A `null` connection
  string is an exception. Using exceptions for both means the caller cannot tell them apart
  and the logs cannot either.
- **`CancellationToken` is threaded to every await.** A token that stops at the handler
  boundary means a client disconnect still costs the full database round trip.

Queries are the mirror image and deliberately thinner: on the read side (`dotnet-query`,
Dapper with read models) a handler may hold SQL and project straight into a DTO. Do not
route reads through the write-side aggregates to feel consistent — that is the cost CQRS
was adopted to avoid.

A licensing note worth surfacing rather than discovering during an upgrade: MediatR and
AutoMapper moved to a commercial licence for their newer major versions while older
versions remain under their original terms. Check the pinned version and your
organization's position before proposing an upgrade, and mention it if you propose adding
either library to a project that does not already have it.

## DTO mapping, and the trap that silently writes `null`

The most expensive bug in this stack is not a crash. It is a property that quietly arrives
as `null` because a reflection-based mapper was never told about it, and nothing —
compiler, test, or code review — is looking.

```csharp
public sealed class OrderProfile : Profile
{
    public OrderProfile()
    {
        CreateMap<CreateOrderCommand, Order>()
            .ForMember(d => d.PlacedAtUtc, o => o.MapFrom(_ => DateTime.UtcNow))
            .ForMember(d => d.Status,      o => o.MapFrom(_ => OrderStatus.Pending))
            .ForMember(d => d.Id,          o => o.Ignore());
    }
}
```

A developer adds `DiscountCode` to the command, to the entity, to the table, and to the
API contract. The feature ships with the discount always empty. Three separate faces of the
same trap produce that:

1. **The names do not quite match.** `DiscountCode` on the command, `Discount` on the
   entity. Convention mapping matches by name, so nothing maps, and the destination keeps
   its default.
2. **Something already suppresses the warning.** An explicit `Ignore()`, or an
   `ForAllOtherMembers(o => o.Ignore())` added years ago to silence a validation failure,
   also silences this one — forever, for every property added afterwards.
3. **The chain has more than one hop.** `Command -> Entity -> OrderDto` with two profiles.
   Updating one hop and not the other leaves the value populated in the debugger at the
   point everyone looks at, and null by the time it reaches the client.

The guard is a test, and it belongs in every solution that uses a mapper:

```csharp
[Fact]
public void Mapping_configuration_is_valid() =>
    new MapperConfiguration(c => c.AddMaps(typeof(OrderProfile).Assembly), NullLoggerFactory.Instance)
        .AssertConfigurationIsValid();
```

That fails the build the moment a destination member has no source and no explicit
`Ignore()`. Its limit is exactly the second face above: it cannot tell an intentional
`Ignore()` from a stale one, so every `Ignore()` deserves a trailing comment saying why.
Declaring the map with `CreateMap<CreateOrderCommand, Order>(MemberList.Source)` inverts the
check to "every field of the command landed somewhere," which is usually the question you
actually care about on the write side.

Where the mapping crosses a contract boundary that other teams consume, prefer a
hand-written `static OrderDto FromDomain(Order order)`. It costs a few lines, it is a
compile error rather than a runtime `null` when the shape changes, and it can be read
without knowing the mapper's conventions.

## Repository conventions

```csharp
public interface IOrderRepository            // in the Application layer, beside its consumers
{
    Task<Order?> GetAsync(Guid id, CancellationToken ct);
    Task AddAsync(Order order, CancellationToken ct);
}
```

- The interface lives with the code that uses it; the EF Core implementation lives in
  Infrastructure. That direction of dependency is the point of the split — the application
  layer must not reference the persistence package.
- Return materialized domain objects, never `IQueryable`. An `IQueryable` crossing the
  boundary means the caller decides when the query runs, and the failure mode is a
  `DbContext` disposed before enumeration or an N+1 that only reproduces under load.
- The repository does not call `SaveChanges`. The handler owns the unit of work, because it
  is the only thing that knows where the transaction ends.
- Reads are `AsNoTracking()` and project with `Select` into the exact shape needed. Loading
  a whole aggregate to render three columns is the most common performance defect in this
  stack, and it is invisible until the table grows.
- Repositories return `null` for "not found" and let the handler translate that into a
  `Result`. A repository that throws `NotFoundException` forces every caller into a
  try/catch even where absence is expected.

## Test layout (xUnit)

Mirror the source tree: `Orders.Application` is tested by `Orders.Application.Tests`, and
`CreateOrderCommandHandlerTests` sits at the path the handler sits at. When a reviewer can
predict the test file's path from the source file's path, missing tests become visible.

```csharp
public sealed class CreateOrderCommandHandlerTests
{
    private readonly IOrderRepository _orders = Substitute.For<IOrderRepository>();

    [Fact]
    public async Task Persists_the_order_and_returns_its_id()
    {
        var handler = new CreateOrderCommandHandler(_orders, _unitOfWork, NullLogger<...>.Instance);
        var result = await handler.Handle(new CreateOrderCommand(customerId, lines), default);

        Assert.True(result.IsSuccess);
        await _orders.Received(1).AddAsync(Arg.Any<Order>(), Arg.Any<CancellationToken>());
    }
}
```

- `[Theory]` with `[InlineData]` for value variations; `[MemberData]` once the cases need
  types that attributes cannot express. A loop inside a `[Fact]` reports one failure for
  five cases and stops at the first.
- `IClassFixture<T>` for setup shared within a class, `ICollectionFixture<T>` for setup
  shared across classes — a database container is the collection case, and without it xUnit
  runs those classes in parallel against the same database.
- Constructor is the setup, `IAsyncLifetime` when setup must await. There is no
  `[SetUp]` in xUnit, and reaching for a static to emulate one creates order-dependent
  tests that pass locally and fail on CI.
- Never write `async void` on a test. xUnit cannot observe it, so the assertion failure is
  swallowed and the test reports green.
