"""Install explicitly mounted Glue extension wheels before service startup.

Python packaging and subprocess references:
- https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
- https://docs.python.org/3/library/subprocess.html#subprocess.run
"""

from __future__ import annotations

import argparse
import logging
import site
import subprocess
import sys
from pathlib import Path

from mystack_aws_protocol import ConfigurationError, load_configuration
from mystack_aws_protocol.observability import configure_logging, log_event

from .config import GlueSettings

_LOGGER = logging.getLogger(__name__)


def install_mounted_extensions(settings: GlueSettings) -> None:
    extensions = settings.extensions
    if not extensions.enabled:
        log_event(
            _LOGGER,
            logging.INFO,
            "extension.install.skipped",
            service="glue",
            reason="disabled",
        )
        return
    wheels_directory = extensions.wheels_directory.expanduser().resolve()
    install_directory = extensions.install_directory.expanduser().resolve()
    _validate_install_directory(install_directory)
    wheels = tuple(sorted(wheels_directory.glob("*.whl"))) if wheels_directory.is_dir() else ()
    if not wheels:
        log_event(
            _LOGGER,
            logging.INFO,
            "extension.install.skipped",
            service="glue",
            reason="no-mounted-wheels",
            wheels_directory=str(wheels_directory),
            configured_provider_count=len(extensions.providers),
            fix_hint=("Mount provider wheels here or preinstall their entry points in the image."),
        )
        return
    install_directory.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--no-deps",
        "--upgrade",
        "--target",
        str(install_directory),
        *(str(wheel) for wheel in wheels),
    ]
    log_event(
        _LOGGER,
        logging.INFO,
        "extension.install.started",
        service="glue",
        wheel_count=len(wheels),
        wheel_names=[wheel.name for wheel in wheels],
        install_directory=str(install_directory),
        timeout_seconds=extensions.install_timeout_seconds,
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=extensions.install_timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        log_event(
            _LOGGER,
            logging.ERROR,
            "extension.install.timed_out",
            service="glue",
            wheel_count=len(wheels),
            timeout_seconds=extensions.install_timeout_seconds,
            fix_hint="Increase glue.extensions.install_timeout_seconds or inspect the wheels.",
        )
        raise RuntimeError("Glue extension wheel installation timed out") from error
    if completed.returncode != 0:
        log_event(
            _LOGGER,
            logging.ERROR,
            "extension.install.failed",
            service="glue",
            wheel_count=len(wheels),
            return_code=completed.returncode,
            fix_hint=(
                "Run pip with --no-index --no-deps against the mounted wheels and correct the "
                "package metadata; output is intentionally omitted from shared logs."
            ),
        )
        raise RuntimeError(
            f"Glue extension wheel installation failed with code {completed.returncode}"
        )
    _write_path_file(install_directory)
    log_event(
        _LOGGER,
        logging.INFO,
        "extension.install.completed",
        service="glue",
        wheel_count=len(wheels),
        install_directory=str(install_directory),
    )


def _validate_install_directory(path: Path) -> None:
    if not path.is_absolute() or path in {Path("/"), Path.home().resolve()}:
        raise ConfigurationError(
            "glue.extensions.install_directory must be a dedicated absolute directory"
        )


def _write_path_file(install_directory: Path) -> None:
    candidates = site.getsitepackages()
    if not candidates:
        raise RuntimeError("Python did not report a site-packages directory")
    path_file = Path(candidates[0]) / "mystack-glue-extensions.pth"
    log_event(
        _LOGGER,
        logging.INFO,
        "extension.path_file.write.started",
        service="glue",
        path_file=str(path_file),
    )
    path_file.write_text(f"{install_directory}\n", encoding="utf-8")
    log_event(
        _LOGGER,
        logging.INFO,
        "extension.path_file.write.completed",
        service="glue",
        path_file=str(path_file),
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Install mounted Mystack Glue extension wheels")
    parser.add_argument("--config", help="Path to the versioned Mystack YAML configuration")
    arguments = parser.parse_args()
    loaded = load_configuration(arguments.config)
    settings = GlueSettings.from_configuration(loaded)
    level = str(loaded.document.get("logging", {}).get("level", "INFO"))
    configure_logging("glue-extension-bootstrap", level)
    install_mounted_extensions(settings)


if __name__ == "__main__":
    run()
