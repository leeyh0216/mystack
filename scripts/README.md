# Automation entry points

`scripts/` contains repository automation, not service runtime code. Use the grouped directories
first; root-level files remain only for cross-cutting bootstrap, architecture, and packaging tasks.

| Area | Location | Purpose |
| --- | --- | --- |
| Compatibility | [`compatibility/`](compatibility/) | Collect pytest annotations, compile CI matrices, classify API coverage, validate Glue error contracts, and run one selected compatibility case. |
| Release | [`release/`](release/) | Resolve release policy, version updates, GitHub release/tag actions, and repository governance. |
| Quality | [`quality/`](quality/) | Documentation, configuration, upstream-model, and dependency-boundary verification. |
| Development | [`development/`](development/) | Local environment setup and reproducible build inputs. |

Run stable commands through `make`; CI uses the same command surface. Do not place service runtime
logic here: service-owned code belongs under its component's `src/`, while test-only workloads belong
under `tests/`.

