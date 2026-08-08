"""Emit the actual EMR image runtime inventory without environment values.

Official runtime sources:
- Corretto 17: https://docs.aws.amazon.com/corretto/latest/corretto-17-ug/amazon-linux-install.html
- Spark configuration: https://spark.apache.org/docs/3.5.4/configuration.html
- Python venv: https://docs.python.org/3.11/library/venv.html
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import pwd
import shutil
import ssl
import subprocess
import sys
from pathlib import Path
from typing import Any


def inventory() -> dict[str, Any]:
    service_user = pwd.getpwnam("hadoop")
    java_home = Path(os.getenv("JAVA_HOME", "/usr/lib/jvm/jre-17"))
    spark_home = Path(os.getenv("SPARK_HOME", "/opt/spark"))
    return {
        "schema_version": 1,
        "base_os": _os_release(),
        "service_identity": {
            "user": service_user.pw_name,
            "uid": service_user.pw_uid,
            "gid": service_user.pw_gid,
            "home": service_user.pw_dir,
            "shell": service_user.pw_shell,
            "initialization_user": "root",
        },
        "java": {
            "java_home": str(java_home),
            "java": _executable("java"),
            "keytool": _executable("keytool"),
            "version": _version(["java", "-version"]),
            "default_trust_store": str(java_home / "lib/security/cacerts"),
            "system_trust_store": "/etc/pki/ca-trust/extracted/java/cacerts",
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "virtualenv_module": "venv",
            "site_packages": _site_packages(),
            "packages": _packages(),
            "ca_paths": _ca_paths(),
        },
        "spark": {
            "spark_home": str(spark_home),
            "spark_submit": str(spark_home / "bin/spark-submit"),
            "release": _read_first_line(spark_home / "RELEASE"),
            "ivy_cache": "/home/hadoop/.ivy2",
            "master": "local[*] (configured in config/mystack.yaml)",
        },
        "aws_cli": {
            "executable": _executable("aws"),
            "version": _version(["aws", "--version"]),
        },
        "paths": {
            "working_directory": "/opt/mystack",
            "state_directory": "/var/lib/mystack/emr",
            "configuration": "/etc/mystack/mystack.yaml",
            "prestart_directory_default": "/etc/mystack/emr-prestart.d",
            "inventory": "/opt/mystack/runtime-inventory.json",
            "writable_as_hadoop": ["/var/lib/mystack/emr", "/home/hadoop", "/home/hadoop/.ivy2"],
        },
        "environment_names": [
            "AWS_CA_BUNDLE",
            "AWS_ENDPOINT_URL",
            "AWS_ENDPOINT_URL_S3",
            "HTTPS_PROXY",
            "HTTP_PROXY",
            "JAVA_HOME",
            "JAVA_TOOL_OPTIONS",
            "MYSTACK_CONFIG_FILE",
            "MYSTACK_EMR_PRESTART_DIR",
            "MYSTACK_EMR_PRESTART_ENABLED",
            "NO_PROXY",
            "PYSPARK_PYTHON",
            "REQUESTS_CA_BUNDLE",
            "SPARK_HOME",
            "SSL_CERT_FILE",
        ],
        "official_sources": [
            "https://docs.aws.amazon.com/corretto/latest/corretto-17-ug/amazon-linux-install.html",
            "https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html",
            "https://docs.docker.com/reference/dockerfile/#entrypoint",
            "https://docs.python.org/3.11/library/venv.html",
            "https://spark.apache.org/docs/3.5.4/configuration.html",
        ],
    }


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write deterministic JSON to this file")
    args = parser.parse_args()
    document = json.dumps(inventory(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(document)
        return
    args.output.write_text(document, encoding="utf-8")


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "NAME", "VERSION_ID", "PRETTY_NAME"}:
            values[key.lower()] = value.strip('"')
    return values


def _packages() -> list[dict[str, str]]:
    versions = {
        distribution.metadata["Name"]: distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    return [
        {"name": name, "version": versions[name]} for name in sorted(versions, key=str.casefold)
    ]


def _site_packages() -> list[str]:
    return sorted({str(Path(value).resolve()) for value in sys.path if "site-packages" in value})


def _ca_paths() -> dict[str, str | None]:
    paths = ssl.get_default_verify_paths()
    return {
        "cafile": paths.cafile,
        "capath": paths.capath,
        "openssl_cafile_env": paths.openssl_cafile_env,
        "openssl_capath_env": paths.openssl_capath_env,
    }


def _executable(name: str) -> str | None:
    value = shutil.which(name)
    return str(Path(value).resolve()) if value else None


def _version(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = completed.stdout.strip() or completed.stderr.strip()
    lines = [
        line for line in output.splitlines() if not line.startswith("Picked up JAVA_TOOL_OPTIONS:")
    ]
    return lines[0] if lines else None


def _read_first_line(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return None
