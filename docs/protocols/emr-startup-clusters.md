<!-- doc-id: protocols/emr-startup-clusters -->
<!-- lang: en -->

[한국어](emr-startup-clusters.ko.md) | [English](emr-startup-clusters.md)

# EMR startup cluster file

<!-- toc:start -->
## Contents

- [Versioned format](#versioned-format)
- [Validation and startup semantics](#validation-and-startup-semantics)
- [Published-image Compose usage](#published-image-compose-usage)
- [Diagnose and maintain](#diagnose-and-maintain)
- [Official sources](#official-sources)
<!-- toc:end -->

Mystack can create a reviewed set of process-local EMR clusters before its health endpoint becomes
ready. This is an emulator deployment input, not a new AWS operation. Each `clusters` entry uses the
official [`RunJobFlow` request members](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html),
then enters the same command and lifecycle path as a boto3 request.

<!-- section: format -->
## Versioned format

The root is deliberately small and rejects unknown keys:

```yaml
schema_version: 1
clusters:
  - Name: local-analytics
    ReleaseLabel: emr-7.8.0
    Instances:
      InstanceCount: 1
      KeepJobFlowAliveWhenNoSteps: true
    Applications:
      - Name: Spark
    Tags:
      - Key: provisioned-by
        Value: startup-file
```

Supported entry members are `Name`, `ReleaseLabel`, `Instances`, `Applications`,
`BootstrapActions`, `Steps`, `LogUri`, `ServiceRole`, `VisibleToAllUsers`,
`StepConcurrencyLevel`, and `Tags`. A member may exist in the upstream botocore model and still be
rejected when Mystack does not emulate it. This prevents a valid-looking file from silently losing
intent. The normal [support scope](../support-scope.md) still applies to initial bootstrap actions
and Steps.

<!-- section: validation -->
## Validation and startup semantics

Before creating the first cluster, Mystack parses the complete YAML and validates every entry
against the pinned botocore `RunJobFlow` model, the implemented-member allowlist, configured release
profiles, duplicate names, and Step limits. Any failure prevents the EMR HTTP server from becoming
healthy. No partially validated plan is provisioned.

After validation, the inbound file adapter maps entries to the technology-neutral `CreateCluster`
command and calls the existing application port in file order. It never writes directly to the
repository. Bootstrap actions and initial Steps continue asynchronously through the same queue
driver used by boto3 requests. `ListClusters`, `DescribeCluster`, the management resource endpoint,
and the Console therefore see the same aggregates.

The current EMR repository is process-local. Restarting the EMR container creates the configured
set again with new cluster IDs; it does not reconcile names or preserve old IDs. A deterministic
file fingerprint and configured count are exposed in health and management responses.

<!-- section: docker -->
## Published-image Compose usage

Download the overlay and a sample from the same release tag as the images. Mounting is explicit and
read-only, following Docker's [bind-mount contract](https://docs.docker.com/engine/storage/bind-mounts/):

```bash
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.emr-startup-clusters.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.emr-startup-clusters.yaml
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/config/emr-clusters.example.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > emr-clusters.yaml

export MYSTACK_EMR_STARTUP_CLUSTERS_FILE="$PWD/emr-clusters.yaml"
docker compose -f compose.ghcr.yaml -f compose.emr-startup-clusters.yaml \
  up --detach --wait --wait-timeout 300
```

Alternatively, set `emr.startup_clusters_file` in a mounted main configuration. A relative path is
resolved beside that main configuration file. The nested environment override is
`MYSTACK__EMR__STARTUP_CLUSTERS_FILE`; `null` disables the feature. Edit the external file and
restart EMR to apply an atomic new plan.

<!-- section: diagnose -->
## Diagnose and maintain

Inspect `emr.startup_clusters.load.*`, `emr.startup_clusters.provision.*`, and
`emr.startup_cluster.create.*` structured events. They include source, fingerprint, definition
index, counts, cluster identity, and a fix hint without logging bootstrap arguments or environment
secrets. If a newer boto3/botocore input stops validating, inspect the pinned model manifest and
generic validator first, then update the supported-member set and mapping in
`emr/adapters/inbound/startup.py` and `aws_shapes.py`.

<!-- section: sources -->
## Official sources

- [Amazon EMR RunJobFlow](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
- [Amazon EMR bootstrap actions](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
- [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
