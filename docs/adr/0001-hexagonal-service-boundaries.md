# ADR 0001: Hexagonal service boundaries

[한국어](0001-hexagonal-service-boundaries.ko.md) | English

- Status: Accepted
- Date: 2026-08-08

## Context

The system must grow toward hundreds of AWS operations without coupling protocol parsing, domain behavior, Spark execution, LocalStack, storage and UI concerns. Lower-level modules must never know their callers.

## Decision

Proxy, EMR and Glue are independently deployable Python packages. Each emulator separates Domain, Application, Adapters and Composition Root. Ports are declared in the inward layer that consumes them; adapters implement those ports. Shared code is restricted to AWS wire-protocol mechanics.

Imports are allowed only inward. Architecture tests enforce the rule.

## Consequences

- Domain state machines can be tested without FastAPI, Docker, Spark or LocalStack.
- Replacing in-memory storage with SQLite or a different execution backend does not modify use cases.
- AWS request/response mapping stays at an inbound adapter and cannot leak wire dictionaries throughout the domain.
- Some mapping code is intentionally duplicated between bounded contexts rather than sharing business concepts.

## Official reference

[AWS Prescriptive Guidance: Building hexagonal architectures](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)

