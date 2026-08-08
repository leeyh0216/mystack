<!-- doc-id: evolution -->
<!-- lang: en -->

[한국어](evolution.ko.md) | [English](evolution.md)

# Upstream evolution policy

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

1. Add its exact artifact URL and content digest to `compatibility/cases.yaml`.
2. Add or reuse one runtime profile, runner adapter, compatibility profile, and scenario set.
3. Add one explicit case and assign every new required case/scenario to one bilingual acceptance
   area. Do not add a version axis that creates unreviewed combinations.
4. Run `make compatibility-generate`, review the JSON, exact-version tables, and generated
   release-acceptance tables, then run
   `make compatibility-case CASE=<id>`.
5. Run `make compatibility-check`. CI derives a new job from the generated `include` entry without
   workflow source changes.

The compiler fails before tests for unknown fields, duplicate IDs, mutable sources, invalid digests,
unknown adapters, runtime/config mismatches, stale model fingerprints, missing test nodes, unsafe
evidence paths, and undocumented required cases or scenarios. A case records exact versions,
scenario/operation IDs, model fingerprints, and a deterministic evidence hash so logs point
maintainers at the broken boundary.

<!-- section: checklist -->
## Compatibility change checklist

- Link the direct official source.
- Update Korean and English docs together.
- Update the manifest/coverage intentionally.
- Add positive and modeled-error contracts.
- Add before/after/error logs at any new side-effect boundary.
- Preserve a previous runtime profile when compatibility requires it.

References: [official botocore models](https://github.com/boto/botocore/tree/develop/botocore/data), [GitHub Dependabot configuration](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates), [AWS hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html).
