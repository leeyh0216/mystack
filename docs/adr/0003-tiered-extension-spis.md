<!-- doc-id: adr-0003-tiered-extension-spis -->
<!-- lang: en -->

[한국어](0003-tiered-extension-spis.ko.md) | [English](0003-tiered-extension-spis.md)

# ADR 0003: Tiered in-process extension SPIs

- Status: Accepted
- Date: 2026-08-08

<!-- section: context -->
## Context

An operation handler that receives only a payload and next handler cannot inspect
Mystack-managed Catalog state. Giving every extension the concrete repository
would instead bypass application invariants and couple every user extension to
internal refactoring.

Python discovers entry points declared by installed distributions through
[`importlib.metadata.entry_points`](https://docs.python.org/3/library/importlib.metadata.html#entry-points).
PyPA documents the pattern in its [plugin discovery
guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
and [entry-points specification](https://packaging.python.org/en/latest/specifications/entry-points/).

<!-- section: decision -->
## Decision

Provide three SPIs with different authority and compatibility contracts over one
common asynchronous operation chain.

| SPI | Injected objects | Mutation path | Compatibility promise |
| --- | --- | --- | --- |
| `stable` | immutable Catalog snapshots and a capability facade | application use cases | maintained within the SPI major version |
| `application` | `CatalogApplication` and public domain types | direct application-service calls | Mystack minor-version scope |
| `unsafe` | application, repository, clock, and settings | concrete-object calls | exact Mystack version only |

Each SPI has a separate entry-point namespace and provider `Protocol`. The
composition root injects its context once and the provider returns operation
middleware. Domain and application modules never import a provider or plugin
implementation. This follows the [AWS hexagonal architecture
guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html).

<!-- section: execution -->
## Execution contract

- Middleware receives the operation call and next handler. Omitting the next
  call replaces built-in behavior.
- Middleware may run before and after the next handler or translate a service error.
- One middleware may invoke its next handler at most once.
- Configured priority and ID determine execution order.
- Every invocation has a configurable timeout.
- Startup validates the entry point, SPI API version, operation names, duplicate
  IDs, the `application` minor version, unsafe permission, and the exact unsafe version.
- Before, after, and failure logs carry SPI, extension ID, operation, timeout,
  and a fix hint without request values or credentials.

An `application` provider declares the installed `major.minor`. `unsafe` provides no process
isolation or recovery. Loading requires both a global opt-in and the provider's exact Mystack
version.

<!-- section: packaging -->
## Packaging and Docker

Users mount wheels that declare entry points into a read-only directory. Glue's
container startup installs those wheels into a separate configured directory.
Automatic dependency resolution is disabled so a plugin cannot mutate Mystack's
base environment. Required dependency wheels must also be mounted explicitly.

When extensions are disabled, startup skips installation and entry-point
discovery. The built-in handler chain and public AWS behavior remain unchanged.

<!-- section: consequences -->
## Consequences

- Ordinary error corrections use `stable` to inspect state and translate a service error.
- Deeper domain behavior can use `application`.
- Experiments and emergency repairs can use `unsafe`, with upgrade responsibility
  assigned to the plugin author.
- All tiers reuse before, after, error-only, and replacement composition semantics.
- Remote sidecars and process isolation remain outside this decision.

<!-- section: alternatives -->
## Alternatives considered

- Payload-only handlers were rejected because they cannot inspect managed state.
- A single concrete-repository SPI was rejected because it loses both invariants
  and long-term compatibility.
- A global service locator was rejected because it hides dependencies and weakens
  test isolation.

<!-- section: sources -->
## Official references

- [Python entry-point discovery](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [PyPA plugin discovery guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [PyPA entry-points specification](https://packaging.python.org/en/latest/specifications/entry-points/)
- [AWS hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
