<!-- doc-id: contributing -->
<!-- lang: en -->

[한국어](CONTRIBUTING.ko.md) | [English](CONTRIBUTING.md)

# Contributing to Mystack

<!-- toc:start -->
## Contents

- [Define scope before implementation](#define-scope-before-implementation)
- [Architecture rules](#architecture-rules)
- [Provenance and compatibility rules](#provenance-and-compatibility-rules)
- [Bilingual documentation](#bilingual-documentation)
- [Tests and timeouts](#tests-and-timeouts)
- [Bilingual issues](#bilingual-issues)
- [Issue-sized changes and publication](#issue-sized-changes-and-publication)
- [Change description](#change-description)
<!-- toc:end -->

<!-- section: scope -->
## Define scope before implementation

Identify the public operation, request and response structures, state transition,
and error code before implementing AWS behavior. Start with the [Amazon EMR API
Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue
Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), and
the [pinned botocore service model](https://github.com/boto/botocore/tree/develop/botocore/data).
Keep the exact authoritative link close to the implementation, test, and docs.

Distinguish AWS service errors from Mystack defects. For example,
`AlreadyExistsException` when recreating an existing partition is a service
contract to reproduce.

<!-- section: architecture -->
## Architecture rules

- Keep domain and application layers independent of FastAPI, boto3, Spark,
  Docker, and persistence implementations.
- Put external systems and user extensions behind stable ports or public
  extension APIs.
- Preserve invariants and state transitions in the application layer. Adapters
  and extensions do not mutate persistence implementations directly.
- Reject unsupported fields with the official error structure instead of
  silently ignoring them.
- Update the versioned file model, defaults, validation, and example together
  when adding configuration.
- Log before, after, and failure phases around side effects without credentials
  or raw request bodies.

See the [AWS hexagonal architecture
guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
and this repository's [architecture document](docs/architecture.md).

<!-- section: provenance -->
## Provenance and compatibility rules

- Use primary AWS sources for service contracts.
- Record the tested botocore version and service-model fingerprint for SDK behavior.
- Link exact official release documentation or source tags for Spark, Hive, and
  Iceberg behavior.
- Store observed cloud responses only as sanitized validation evidence.
- Give compatibility workarounds an applicable version, fix hint, and removal condition.

<!-- section: bilingual-docs -->
## Bilingual documentation

Update Korean and English maintainer documents in the same change:

- `README.md` and `README.ko.md`;
- `CONTRIBUTING.md` and `CONTRIBUTING.ko.md`;
- `docs/name.md` and `docs/name.ko.md`.

Counterparts use the same `doc-id`, ordered `section` markers, and official
source URLs. Every page contains language-switch links. Korean documents follow
the [Korean technical writing standard](docs/korean-writing-style.md).

<!-- section: tests -->
## Tests and timeouts

Run the nearest layer first and then the full contract suites:

```bash
make docs
make contract
make e2e
```

Test success, official errors, state transitions, and boundaries. Validate the
public protocol with boto3 and AWS CLI. Validate Spark integration with real
Spark, Glue Catalog, Hive, and Iceberg execution paths. Every test has an
explicit timeout. See the [testing strategy](docs/testing.md) for local and CI
values.

<!-- section: issues -->
## Bilingual issues

Every issue body has equivalent `## English` and `## 한국어` sections. Keep scope,
acceptance criteria, exclusions, dependencies, and official sources in parity.
Titles may remain English. See the [GitHub Issues
documentation](https://docs.github.com/issues/tracking-your-work-with-issues/using-issues/creating-an-issue).

<!-- section: workflow -->
## Issue-sized changes and publication

- Create a bilingual issue with a milestone and classification labels before implementation.
- Branch from `develop` as `feature/<issue>-<topic>` and open the implementation PR back to
  `develop`. Move reviewed batches from `develop` to `main` only with a new stable version.
- Complete implementation, tests, user documentation, and maintainer documentation for that issue
  together.
- Do not accumulate completed changes in the working tree. After local checks pass, create one
  logical commit referencing the issue number, push the feature branch, and inspect CI.
- Close the issue only after its acceptance criteria and CI pass. Split the next concern into a new
  issue and commit.

PRs and feature branches cannot publish. A successful accepted `develop` commit publishes a unique
snapshot, while a successful accepted `main` commit publishes the stable version. Follow the
[versioning guide](docs/versioning.md); never create the release tag by hand.

Use GitHub's [issue-closing commit
mechanism](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
when appropriate.

<!-- section: change-description -->
## Change description

A pull request states:

- supported client and runtime versions;
- authoritative documentation and service models;
- selected layer and dependency direction;
- success and error behavior;
- structured logging and diagnostic location;
- tests run with their timeouts;
- remaining limitations and follow-up work.

Do not close an issue until all acceptance criteria are exercised.
