<!-- doc-id: adr-0003-pep420-namespace-packages -->
<!-- lang: en -->

[한국어](0003-pep420-namespace-packages.ko.md) | [English](0003-pep420-namespace-packages.md)

# ADR-0003: Compose Python distributions under a PEP 420 namespace

<!-- toc:start -->
## Contents

- [Status](#status)
- [Context](#context)
- [Decision](#decision)
- [Consequences](#consequences)
- [Verification](#verification)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: status -->
## Status

Accepted on 2026-08-08. This decision replaces the previous top-level
`mystack_aws_protocol`, `mystack_proxy`, `mystack_emr`, and `mystack_glue` import packages.

<!-- section: context -->
## Context

Mystack publishes four independently built Python distributions, but they belong to one product.
Separate top-level import names obscured that ownership and made future services likely to add more
unrelated global names. Python defines implicit namespace packages for portions supplied by multiple
distributions, and the uv build backend supports dotted module names for this layout.

<!-- section: decision -->
## Decision

Keep the distribution names and use these import paths:

| Distribution | Import package |
| --- | --- |
| `mystack-aws-protocol` | `mystack.aws_protocol` |
| `mystack-proxy` | `mystack.proxy` |
| `mystack-emr` | `mystack.emr` |
| `mystack-glue` | `mystack.glue` |

No distribution may contain `mystack/__init__.py`. Each member declares its dotted
`tool.uv.build-backend.module-name`, and console scripts point directly at the new module. No
compatibility shim is provided because these Python packages are repository-internal.

All intra-project imports use their complete `mystack.aws_protocol`, `mystack.proxy`,
`mystack.emr`, or `mystack.glue` path. Relative imports are forbidden even within one package so a
reader and the architecture checks see the dependency owner without resolving package depth.

<!-- section: consequences -->
## Consequences

All product modules now have a visible shared owner without coupling their service contexts.
Additional distributions can contribute another `mystack.<service>` portion. A wheel that adds the
namespace-root initializer could silently break co-installation, so source-tree imports alone are
insufficient verification. Ruff `TID252` rejects every relative import locally, in pre-commit, and
in CI. Tests construct their own fixtures or import an explicitly owned helper instead of importing
sibling test modules.

<!-- section: verification -->
## Verification

`make package-check` builds every workspace distribution, inspects each wheel, installs all wheels
together in a temporary virtual environment, and resolves every configured module. Its subprocess
deadline comes from `tests.package_smoke_timeout_seconds`. Architecture tests also reject a
namespace-root initializer and compare module paths with each member's build configuration.

<!-- section: sources -->
## Official sources

- [Python namespace package specification](https://docs.python.org/3/reference/import.html#namespace-packages)
- [Python virtual environments](https://docs.python.org/3/library/venv.html)
- [uv namespace package configuration](https://docs.astral.sh/uv/concepts/build-backend/#namespace-packages)
- [Ruff relative-import rule](https://docs.astral.sh/ruff/rules/relative-imports/)
