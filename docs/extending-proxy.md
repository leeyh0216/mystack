<!-- doc-id: extending-proxy -->
<!-- lang: en -->

[한국어](extending-proxy.ko.md) | [English](extending-proxy.md)

# Add another emulator without changing Proxy code

<!-- toc:start -->
## Contents

- [Procedure](#procedure)
- [Protocol change versus service change](#protocol-change-versus-service-change)
<!-- toc:end -->

The Proxy route registry uses official AWS request evidence: `X-Amz-Target`, the SigV4 credential-scope service, and service host prefixes. See [Signature Version 4](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html) and [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data).

<!-- section: procedure -->
## Procedure

1. Read the official service model metadata: `targetPrefix`, `endpointPrefix`, signing name, protocol, JSON version, and API version.
2. Build the new emulator as an independent service with its own Domain/Application/Adapters.
3. Add one YAML entry:

```yaml
proxy:
  routes:
    - name: athena
      backend_url: http://athena:8080
      target_prefixes: [AmazonAthena]
      signing_names: [athena]
      host_prefixes: [athena]
```

4. Add the container to Compose on the internal network; do not expose another public AWS port.
5. Add a route detector test and a boto3 black-box contract through the Proxy.
6. Add Korean/English protocol, scope, configuration, and operation coverage documents.
7. Add before/after/error logs at new storage, process, network, or container side effects.

No Proxy `if service == ...` branch is allowed. Duplicate target/signing/host claims fail configuration validation at startup.

<!-- section: evolution -->
## Protocol change versus service change

- Generic AWS JSON serialization changes belong in `shared`.
- A service-specific shape mapping belongs in the new inbound adapter.
- Business states and rules belong in Domain/Application.
- Endpoint and deployment values belong only in YAML or deployment overrides.

Clients select the same public URL using the [official custom endpoint mechanism](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html).
