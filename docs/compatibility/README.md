<!-- doc-id: compatibility-index -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Compatibility reference for maintainers

<!-- toc:start -->
## Contents

- [Read in this order](#read-in-this-order)
- [Use CI reports only when needed](#use-ci-reports-only-when-needed)
- [What CI produces](#what-ci-produces)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
This directory contains the short reference documents that maintainers read first. Detailed
verification reports are CI/local build output, not repository documentation. Start with these
pages when changing a supported API operation, test scenario, or release condition.

<!-- section: reading-order -->
## Read in this order

1. [Client and library compatibility](client-matrix.md) — supported clients, exact versions, and
   the vertical workflow each client proves.
2. [API compatibility coverage](api-coverage.md) — implemented operations and the difference
   between compatible, partial, protocol-only, and out-of-scope APIs.
3. [Support scope](../support-scope.md) — product commitments and exclusions.
4. [Glue error decisions](../protocols/glue/glue-error-decisions.md) — why an operation returns a given
   modeled error and how its precedence is chosen.

## Use CI reports only when needed

You do not need a CI report to run a client or understand the supported surface. For a maintenance
question, start with the document below and inspect the job artifact only when the source and test
do not answer it:

| Question | Start here | CI detail, if needed |
| --- | --- | --- |
| Can my client path be used? | [Client and library compatibility](client-matrix.md) | Compatibility case report |
| Is a particular EMR or Glue operation implemented? | [API compatibility coverage](api-coverage.md) | Full API classification |
| Why does a Glue request return this error? | [Glue error decisions](../protocols/glue/glue-error-decisions.md) | Error decision report |
| What must pass before publishing? | [Support scope](../support-scope.md) | Release acceptance report |

<!-- section: generated-artifacts -->
## What CI produces

CI writes the following reproducible files under ignored `ci-artifacts/compatibility/`. They are
attached to the workflow run when useful and are never hand-edited or committed:

| Report | Why it exists | Consumer |
| --- | --- | --- |
| Client matrix | Exact test/client/runtime combinations selected by CI | CI matrix and release review |
| Annotation report | Links an annotated test to the operations and scenarios it proves | CI collection and maintainers |
| API coverage | Full pinned botocore inventory and classification | Model-drift gate |
| Glue errors | Exhaustive modeled error and precedence table | Error-contract gate |
| Release acceptance | Required compatibility cases for publication | Release gate |

Source policies remain in `contracts/`; tests declare what they verify. Generation is deterministic
and CI runs it before selecting required compatibility cases. Developers normally run
`make compatibility-check` to detect a source/artifact mismatch; they do not hand-edit reports.

See [`contracts/README.md`](../../contracts/README.md) for the source-of-truth files and the
command to run after a change.

<!-- section: sources -->
## Official sources

- [AWS Glue API reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Amazon EMR API reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
