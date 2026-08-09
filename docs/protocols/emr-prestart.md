<!-- doc-id: emr-prestart -->
<!-- lang: en -->

[한국어](emr-prestart.ko.md) | [English](emr-prestart.md)

# Configure the EMR image before Mystack starts

Use this operator-only hook when a published EMR image needs enterprise CA certificates, proxy
variables, or another machine-level prerequisite before its service, bootstrap actions, and Spark
Steps start. It is disabled by default and runs only in the EMR container.

<!-- section: quick-start -->
## Start a published image with reviewed scripts

Download the base Compose file, this overlay, and the example scripts from the same release tag.
Replace the placeholder certificate path before starting. The directory is mounted read-only using
Docker's [bind-mount contract](https://docs.docker.com/engine/storage/bind-mounts/).

```bash
export MYSTACK_IMAGE_TAG=v0.1.3  # replace with a published tag
mkdir -p mystack-runtime/emr-prestart.d && cd mystack-runtime
for path in compose.ghcr.yaml compose.emr-prestart.yaml; do
  gh api -H "Accept: application/vnd.github.raw+json" \
    "repos/leeyh0216/mystack/contents/${path}?ref=${MYSTACK_IMAGE_TAG}" > "${path}"
done
for path in 10-enterprise-ca.sh 20-proxy-environment.sh; do
  gh api -H "Accept: application/vnd.github.raw+json" \
    "repos/leeyh0216/mystack/contents/examples/emr-prestart/${path}?ref=${MYSTACK_IMAGE_TAG}" \
    > "emr-prestart.d/${path}"
done
chmod 0755 emr-prestart.d
chmod 0644 emr-prestart.d/*.sh
export MYSTACK_EMR_PRESTART_SOURCE="$PWD/emr-prestart.d"
docker compose -f compose.ghcr.yaml -f compose.emr-prestart.yaml config --quiet
docker compose -f compose.ghcr.yaml -f compose.emr-prestart.yaml up --detach --wait --wait-timeout 300
```

The examples are templates, not safe defaults: `10-enterprise-ca.sh` deliberately fails until an
operator-controlled certificate is available at its configured path. Do not place secrets, AWS
credentials, downloaded workload files, or unreviewed scripts in this directory.

<!-- section: lifecycle -->
## Lifecycle and identity contract

The container entrypoint begins as `root`, scans `*.sh` once in bytewise filename order, and sources
each script in the same shell. A non-zero result stops the container immediately; later scripts and
the EMR service do not run. Exported variables therefore reach the EMR API process, its `hadoop`
bootstrap children, and Spark children. Non-exported shell variables do not.

After all scripts succeed, the entrypoint restores its working directory and safe field separator,
sets `HOME=/home/hadoop`, and changes supplementary groups, GID, and UID to the fixed `hadoop`
account. It then replaces PID 1 with the configured command. This preserves Docker's
[exec-style ENTRYPOINT signal behavior](https://docs.docker.com/reference/dockerfile/#entrypoint)
while using Python's documented [`setuid`](https://docs.python.org/3.11/library/os.html#os.setuid).
Amazon EMR separately documents that ordinary [bootstrap actions run as Hadoop and use `sudo` for
root work](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html). Pre-start
hooks are an image initialization boundary and are not EMR `BootstrapActions` API entries.

Do not override the EMR container user. Routine debugging should use
`docker compose exec --user hadoop emr ...`; use root only for a deliberate operator diagnosis.

<!-- section: trust -->
## Trust and file checks

Enabling the hook grants every accepted script arbitrary root execution. Mystack rejects a missing
or symlinked directory, a group/world-writable directory, unsafe names, symlinks, non-regular files,
and group/world-writable scripts. A script does not need its executable bit because it is sourced.
These checks reduce accidental substitution; they do not sandbox trusted root code.

The supported knobs are entrypoint environment variables rather than application YAML because they
must be evaluated before Python configuration loading:

| Name | Default | Meaning |
| --- | --- | --- |
| `MYSTACK_EMR_PRESTART_ENABLED` | `false` | Explicit opt-in boolean |
| `MYSTACK_EMR_PRESTART_DIR` | `/etc/mystack/emr-prestart.d` | In-container reviewed directory |
| `MYSTACK_EMR_PRESTART_SOURCE` | none | Host directory required by the Compose overlay |

Use stable numeric filename prefixes such as `10-ca.sh` and `20-environment.sh`. Changing a mounted
file requires a container recreation; hooks are intentionally not hot-reloaded.

<!-- section: certificates -->
## Certificates, proxies, Python, and Java

For an enterprise CA, copy the reviewed PEM certificate into
`/etc/pki/ca-trust/source/anchors`, run `update-ca-trust extract`, and set `SSL_CERT_FILE`,
`REQUESTS_CA_BUNDLE`, and `AWS_CA_BUNDLE` when the corresponding clients need explicit paths. For
Java, import it with the documented [Java 17 `keytool`
interface](https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html). Prefer a copied,
operator-owned truststore plus `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=...` when a mutable
system Java store is undesirable.

Set `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` only with values appropriate for the container
network. Include `proxy`, `emr`, `glue`, `localstack`, loopback names, and required internal domains
in `NO_PROXY` so emulator traffic does not leave the Docker network.

Python 3.11, `venv`, Java 17, `keytool`, Spark 3.5.4, AWS CLI, and the default trust paths are already
installed. A bootstrap-created virtualenv should be owned or readable by `hadoop`, and a later Step
must explicitly select it through `spark.pyspark.python` and `spark.pyspark.driver.python`; Python's
[`venv` documentation](https://docs.python.org/3.11/library/venv.html) explains why shell activation
is not required when the interpreter path is selected directly.

<!-- section: inventory -->
## Inspect the image instead of guessing

Every image includes a build-time inventory at `/opt/mystack/runtime-inventory.json`. Generate the
same schema from a running container without printing environment values:

```bash
docker compose -f compose.ghcr.yaml exec --user hadoop emr mystack-emr-runtime-inventory
docker compose -f compose.ghcr.yaml exec --user hadoop emr \
  python3.11 -m venv /home/hadoop/example-venv
docker compose -f compose.ghcr.yaml exec --user hadoop emr \
  keytool -list -cacerts -storepass changeit
```

The inventory records the actual base OS, service UID/GID/home, resolved executables and versions,
Python packages and CA paths, Spark home/release/Ivy directory, writable paths, and recognized
environment-variable names. It never records environment values. `process_tools.ps` must resolve:
the image installs Amazon Linux `procps-ng` because Spark's
[`bin/load-spark-env.sh`](https://github.com/apache/spark/blob/v3.5.4/bin/load-spark-env.sh)
invokes `ps` while discovering existing processes. A null path is an image contract failure, not a
harmless warning.

<!-- section: diagnostics -->
## Diagnose startup safely

`docker compose logs emr` emits structured `emr.prestart.scan.*`,
`emr.prestart.script.before`, `emr.prestart.script.after`, and
`emr.prestart.script.failed` events. Events include only the basename, permission/owner evidence,
SHA-256 prefix, duration or exit code, and a repair hint. Script contents and environment values are
not logged. A changed fingerprint identifies the file to review when a future image, SDK, Java, or
Spark update breaks initialization.

If the service never starts, read the first failure event, fix that named script, then recreate the
container. If bootstrap or Spark does not see a value, confirm the script used `export` and inspect
PID 1 as root without printing its complete environment. Keep an explicit timeout on Compose waits
and every automated diagnostic command.

<!-- section: scope -->
## Supported scope

Supported behavior is one trusted, lexically ordered, fail-fast source pass before the EMR service,
environment propagation across the privilege boundary, fixed final `hadoop` identity, signal-safe
PID 1 replacement, runtime inventory, and Docker Compose use with published GHCR images. Dynamic
reload, per-cluster hooks, untrusted plugins, secret management, host modification, and Glue image
initialization are not part of this feature.

<!-- section: sources -->
## Official references

- [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- [Docker ENTRYPOINT](https://docs.docker.com/reference/dockerfile/#entrypoint)
- [Amazon EMR bootstrap actions](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
- [Java 17 keytool](https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html)
- [Python venv](https://docs.python.org/3.11/library/venv.html)
- [Python setuid](https://docs.python.org/3.11/library/os.html#os.setuid)
