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
- [Test-declared compatibility evidence](#test-declared-compatibility-evidence)
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

<!-- section: compatibility-evidence -->
## Test-declared compatibility evidence

Compatibility evidence has three owners:

- The EMR/Glue inbound operation inventories own implementation status.
- The annotated `contract` or `e2e` test owns the exact client, runtime,
  scenario, operation, capability, and support claim that it actually proves.
- Typed pytest compatibility annotations, `contracts/compatibility-scope-policy.yaml`, and
  `contracts/api-coverage.generated.json` are the generated compatibility sources
  parity baselines during this migration; the Glue error-condition catalog and
  its precedence policy remain independent required contracts.

Collection verifies the annotated operation union against the literal code-owned
EMR/Glue dispatcher inventories. An annotation cannot make an unregistered
operation compatible, and the botocore-only model-drift job extracts those
literal inventories without importing an emulator.

For a client or runtime change:

1. Create or reuse a typed `CompatibilityProfile` in
   `test_support/compatibility_profiles.py` with exact versions, runtime,
   lane, GitHub Actions job-duration ceiling, and official source URLs.
2. Decorate the smallest real `@pytest.mark.contract` or `@pytest.mark.e2e`
   test with `@compatibility_evidence(...)`. Declare only operations and
   scenarios exercised by that test body.
3. Run `make compatibility-evidence-generate`, review
   `contracts/compatibility-evidence.generated.json` and its Korean/English
   tables, then run `make compatibility-evidence-check`.
4. Run `make compatibility-case CASE=<id>` for the changed case. During the
   migration also run `make compatibility-check`; do not hand-edit generated
   evidence or remove either retained baseline.

The smallest annotation is deliberately close to the test it proves:

```python
import pytest

from test_support.compatibility import compatibility_evidence
from test_support.compatibility_profiles import BOTO3_BOTOCORE_CONTRACT


@pytest.mark.contract
@compatibility_evidence(
    BOTO3_BOTOCORE_CONTRACT,
    scenario_ids=("glue-get-database",),
    operations={"glue": ("GetDatabase",)},
    capabilities=("glue-database-read",),
)
def test_get_database() -> None:
    ...
```

The generator invokes pytest with `--collect-only`: it resolves markers and
node IDs without executing test bodies. It fails when the execution marker,
pinned lock/runtime, API evidence, or legacy case selection drifts. This uses
the [pytest marker](https://docs.pytest.org/en/stable/how-to/mark.html) and
[collection invocation](https://docs.pytest.org/en/stable/how-to/usage.html)
contracts; GitHub Actions consumes the generated `include` entries through the
[shared matrix pattern](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations).
To keep that local check lightweight, it explicitly loads only the configured
timeout/asyncio plugins and rejects `awswrangler` or `pyarrow` imports during
collection. Keep optional clients inside the test body; pytest documents this
[plugin-loading control](https://docs.pytest.org/en/stable/how-to/plugins.html#disabling-plugin-autoloading).
`CompatibilityProfile.expected_duration_minutes` becomes the outer GitHub
Actions job ceiling. It is not a pytest timeout: the collection subprocess is
bounded by `tests.compatibility_collection_timeout_seconds`, and a selected
test body uses its ordinary contract or E2E YAML timeout.

| Failure category | Repair location |
| --- | --- |
| Marker/profile shape or execution marker | The annotated test and `test_support/compatibility.py` |
| Claimed operation is absent from the implementation inventory | The owning `emr` or `glue` `adapters/inbound/aws_*.py` registry, then its test annotation |
| Operation is absent from the pinned botocore model | The inbound handler, pinned model review, and test annotation |
| Locked client/runtime mismatch | `uv.lock`, `test_support/compatibility_profiles.py`, and `config/mystack.yaml` |
| Collection deadline expires | `tests.compatibility_collection_timeout_seconds` or imports made while collecting the annotated test |
| Generated output differs | Run `make compatibility-evidence-generate`; never edit generated files by hand |

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
