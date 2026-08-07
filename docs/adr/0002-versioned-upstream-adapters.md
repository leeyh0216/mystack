# ADR 0002: Versioned upstream adapters and file-driven configuration

[한국어](0002-versioned-upstream-adapters.ko.md) | English

- Status: Accepted
- Date: 2026-08-08

## Context

AWS protocols, botocore models, Spark, Hive, Iceberg, and container bases evolve independently. Hardcoded routes, endpoints, versions, and timeouts make upgrades risky and Docker deployment inflexible.

## Decision

- Commit one schema-versioned YAML configuration and mount it read-only in containers.
- Permit generic `MYSTACK__SECTION__KEY` environment overrides and explicit CLI overrides.
- Isolate botocore models behind the protocol model facade and a committed fingerprint manifest.
- Isolate Spark/Hive/Iceberg combinations in named runtime profiles.
- Detect upstream model drift in a scheduled workflow and report exact changed operations.
- Never log configuration secret values; log source, fingerprint, and redacted override paths.

## Consequences

- New emulator routes require configuration, not Proxy code.
- An upgrade has a named adapter/profile and reproducible E2E evidence.
- Invalid configuration fails at startup with an actionable path.
- Configuration schema migrations require an ADR and bilingual migration notes.

## Official references

- [Docker Compose configs](https://docs.docker.com/reference/compose-file/configs/)
- [Official botocore models](https://github.com/boto/botocore/tree/develop/botocore/data)
- [AWS guidance for adapting hexagonal systems](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)

