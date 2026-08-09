# Configuration ownership

Configuration is file-owned policy. Runtime services read `mystack.yaml`; other files are consumed
only by the listed automation owner.

| File | Owner | Purpose |
| --- | --- | --- |
| [`mystack.yaml`](mystack.yaml) | Proxy, EMR, Glue, and test runners | Runtime ports, routes, storage, timeouts, and supported profile settings. |
| [`sqlite-runtime.json`](sqlite-runtime.json) | Glue image build/runtime verification | SQLite build and capability requirements. |
| [`registry-release.json`](registry-release.json) | `scripts/registry_release.py` | Components, platforms, scanner policy, immutable tags, and publication limits. |
| [`version-files.json`](version-files.json) | `scripts/version.py` | The authoritative list of version-bearing files. |
| [`github-rulesets.json`](github-rulesets.json) | `scripts/github_rulesets.py` | Reviewable main/develop branch protection policy. |
| [`emr-clusters.example.yaml`](emr-clusters.example.yaml) | EMR startup-cluster example | A documented input template, not a default runtime policy. |

See `docs/configuration.md` for runtime settings and `docs/versioning.md` / `docs/container-release.md`
for contributor policy. Do not add generated evidence or runtime data to this directory.

