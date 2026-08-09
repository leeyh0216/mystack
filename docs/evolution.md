<!-- doc-id: evolution -->
<!-- lang: en -->

[한국어](evolution.ko.md) | [English](evolution.md)

# Upstream evolution policy

<!-- toc:start -->
## Contents

- [Change isolation](#change-isolation)
- [Detection and response](#detection-and-response)
- [Adding a client or runtime version](#adding-a-client-or-runtime-version)
- [Compatibility change checklist](#compatibility-change-checklist)
<!-- toc:end -->

Mystack treats botocore, AWS protocols, Spark, Hive, Iceberg, Java, Python, and container bases as independently evolving upstream contracts.

<!-- section: isolation -->
## Change isolation

- Wire metadata/serialization changes belong in `shared/src/mystack/aws_protocol`.
- An EMR or Glue operation shape/semantic change belongs in that service's inbound adapter and use case.
- Spark/Hive/Iceberg changes belong in a versioned runtime profile and its adapter.
- Proxy service additions belong in declarative route configuration, never hardcoded branches.

<!-- section: detection -->
## Detection and response

1. A weekly workflow installs latest botocore and compares it with the committed contract manifest.
2. The report names metadata changes plus added, removed, and shape-changed operations.
3. CI logs include pinned/current versions, model fingerprint, operation, input shape, and `fix_hint`.
4. Dependabot groups AWS SDK updates so protocol changes are reviewed together.
5. Runtime upgrades require a matrix entry and boto3/Spark/Hive/Iceberg E2E evidence.

<!-- section: manifest -->
## Adding a client or runtime version

1. Add or reuse a `CompatibilityProfile` in `test_support/compatibility_profiles.py`. It records
   exact client versions, runtime, lane, outer GitHub Actions job ceiling, and official URLs.
2. Add `@compatibility_evidence(...)` to the smallest real `contract` or `e2e` test that proves
   the client behavior. Its scenario, operation, capability, and support values must describe the
   executed test body rather than a planned feature.
3. Run `make compatibility-evidence-generate` and review the generated JSON and bilingual tables.
   The generator uses [pytest collection](https://docs.pytest.org/en/stable/how-to/usage.html), so
   it resolves the exact node IDs without running test bodies.
4. Run `make compatibility-evidence-check` and
   `make compatibility-case CASE=<id>`. GitHub Actions derives a new isolated job from the
   generated `include` entry without workflow-source changes.
5. During the transition, also run `make compatibility-check`. Keep
   `compatibility/cases.yaml` and `contracts/api-coverage.json` as parity baselines; do not remove
   them or alter the independent Glue error-condition policy in this change.

The annotation compiler fails before execution for an invalid marker shape, missing or mismatched
execution marker, duplicate profile, lock/runtime drift, unknown modeled operation, missing API
evidence, or changed legacy selection. A case records exact versions, scenario/operation IDs,
model fingerprints, and a deterministic evidence hash so logs point maintainers at the broken
boundary.
`tests.compatibility_collection_timeout_seconds` bounds that collection subprocess; the profile's
duration is not a pytest timeout.

<!-- section: checklist -->
## Compatibility change checklist

- Link the direct official source.
- Update Korean and English docs together.
- Update the manifest/coverage intentionally.
- Add positive and modeled-error contracts.
- Add before/after/error logs at any new side-effect boundary.
- Preserve a previous runtime profile when compatibility requires it.

References: [official botocore models](https://github.com/boto/botocore/tree/develop/botocore/data), [GitHub Dependabot configuration](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates), [AWS hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html).
