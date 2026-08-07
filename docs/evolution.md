# Upstream evolution policy

[한국어](evolution.ko.md) | English

Mystack treats botocore, AWS protocols, Spark, Hive, Iceberg, Java, Python, and container bases as independently evolving upstream contracts.

## Change isolation

- Wire metadata/serialization changes belong in `shared/src/mystack_aws_protocol`.
- An EMR or Glue operation shape/semantic change belongs in that service's inbound adapter and use case.
- Spark/Hive/Iceberg changes belong in a versioned runtime profile and its adapter.
- Proxy service additions belong in declarative route configuration, never hardcoded branches.

## Detection and response

1. A weekly workflow installs latest botocore and compares it with the committed contract manifest.
2. The report names metadata changes plus added, removed, and shape-changed operations.
3. CI logs include pinned/current versions, model fingerprint, operation, input shape, and `fix_hint`.
4. Dependabot groups AWS SDK updates so protocol changes are reviewed together.
5. Runtime upgrades require a matrix entry and boto3/Spark/Hive/Iceberg E2E evidence.

## Compatibility change checklist

- Link the direct official source.
- Update Korean and English docs together.
- Update the manifest/coverage intentionally.
- Add positive and modeled-error contracts.
- Add before/after/error logs at any new side-effect boundary.
- Preserve a previous runtime profile when compatibility requires it.

References: [official botocore models](https://github.com/boto/botocore/tree/develop/botocore/data), [GitHub Dependabot configuration](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates), [AWS hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html).

