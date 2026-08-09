# Compatibility contract sources

This directory contains reviewed inputs to compatibility validation. It is not a user guide and it
does not define runtime behavior by itself. Read the human-facing guides in
[`docs/compatibility/`](../docs/compatibility/) first.

## Read in this order

1. `compatibility-scope-policy.yaml` — release scope, supported client scenarios, exclusions, and
   official sources.
2. `glue-error-conditions.yaml` — deterministic Glue error conditions and their precedence.
3. `service-model-manifest.json` — pinned upstream botocore model versions and fingerprints.

GitHub Actions compiles source policy, typed pytest annotations, and pinned models into ignored
`ci-artifacts/compatibility/` reports before it selects compatibility cases. No developer edits
those reports by hand. `make compatibility-check` verifies that the current source produces the
expected local artifact. The human-facing explanation is in `docs/compatibility/`.

## Where to make a change

| Intent | Change first | Then run |
| --- | --- | --- |
| Add or revise a client scenario | Typed compatibility annotation on its test and the scope policy | `make compatibility-generate` |
| Add an implemented API | Adapter, black-box contract test, and error catalog | `make coverage-generate` and `make glue-errors-generate` |
| Update AWS service models | Model manifest workflow/input | `make model-check` and `make compatibility-check` |
| Change what a release guarantees | `compatibility-scope-policy.yaml` | `make compatibility-check` |
