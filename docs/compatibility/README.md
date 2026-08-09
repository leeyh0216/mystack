<!-- doc-id: compatibility-index -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Compatibility reference for maintainers

<!-- toc:start -->
## Contents

- [Read in this order](#read-in-this-order)
- [What CI generates](#what-ci-generates)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
This directory separates the short documents a person should read from the detailed evidence that
CI produces. Start with the user-facing documents; use the generated reports only when changing a
supported operation, test scenario, or release gate.

<!-- section: reading-order -->
## Read in this order

1. [Client and library compatibility](client-matrix.md) — supported clients, exact versions, and
   the vertical workflow each client proves.
2. [API compatibility coverage](api-coverage.md) — implemented operations and the difference
   between compatible, partial, protocol-only, and out-of-scope APIs.
3. [Support scope](../support-scope.md) — product commitments and exclusions.
4. [Glue error decisions](../protocols/glue/glue-error-decisions.md) — why an operation returns a given
   modeled error and how its precedence is chosen.

<!-- section: generated-artifacts -->
## What CI generates

The files named `*.generated.*` are detailed audit outputs, not primary documentation:

| Artifact | Why it exists | Consumer |
| --- | --- | --- |
| Client matrix | Exact test/client/runtime combinations selected by CI | CI matrix and release review |
| Annotation evidence | Links an annotated test to the operations and scenarios it proves | CI collection and maintainers |
| API coverage | Full pinned botocore inventory and classification | Model-drift gate |
| Glue errors | Exhaustive modeled error and precedence table | Error-contract gate |
| Release acceptance | Required compatibility cases for publication | Release gate |

Source policies remain in `contracts/`; tests declare the evidence. Generation is deterministic and
CI verifies it before running required compatibility cases. Developers normally run
`make compatibility-check` to detect drift; they do not hand-edit generated files.

<!-- section: sources -->
## Official sources

- [AWS Glue API reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Amazon EMR API reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
