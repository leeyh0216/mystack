#!/usr/bin/env python3
"""Generate or verify the pinned ANTLR4 Glue expression parser.

Official references:
- https://github.com/antlr/antlr4/blob/4.13.2/doc/getting-started.md
- https://www.antlr.org/download.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import tempfile
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_LOCK = _ROOT / "tools/antlr/glue-partition-expression.lock.json"
_GRAMMAR = _ROOT / "glue/grammar/GluePartitionExpression.g4"
_DESTINATION = _ROOT / "glue/src/mystack/glue/application/partition_expression/generated"
_LOGGER = logging.getLogger("mystack.antlr")


def _event(name: str, **fields: object) -> None:
    _LOGGER.info(json.dumps({"event": name, **fields}, sort_keys=True))


def _download_jar(lock: dict[str, object], destination: Path) -> None:
    url = str(lock["url"])
    _event("antlr.download.before", url=url, version=lock["version"])
    with urllib.request.urlopen(
        url,
        timeout=float(lock["download_timeout_seconds"]),
    ) as response:
        destination.write_bytes(response.read())
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    if digest != lock["sha256"]:
        raise RuntimeError(
            f"ANTLR artifact digest mismatch: expected {lock['sha256']}, got {digest}"
        )
    _event("antlr.download.after", sha256=digest, bytes=destination.stat().st_size)


def _generate(lock: dict[str, object], output: Path, jar: Path) -> dict[str, bytes]:
    command = [
        "java",
        "-jar",
        str(jar),
        "-Dlanguage=Python3",
        "-no-listener",
        "-Xexact-output-dir",
        "-o",
        str(output),
        _GRAMMAR.name,
    ]
    _event("antlr.generate.before", grammar=str(_GRAMMAR), version=lock["version"])
    subprocess.run(
        command,
        check=True,
        cwd=_GRAMMAR.parent,
        timeout=float(lock["generation_timeout_seconds"]),
    )
    generated = {
        path.name: _normalize_generated_source(path.read_bytes())
        for path in sorted(output.glob("*.py"))
    }
    if not generated:
        raise RuntimeError("ANTLR generation produced no Python sources")
    _event("antlr.generate.after", files=sorted(generated))
    return generated


def _normalize_generated_source(content: bytes) -> bytes:
    """Remove generator whitespace variance while preserving executable source."""
    text = content.decode("utf-8")
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return ("\n".join(lines) + "\n").encode()


def _check(generated: dict[str, bytes]) -> None:
    committed = {
        path.name: path.read_bytes()
        for path in sorted(_DESTINATION.glob("*.py"))
        if path.name != "__init__.py"
    }
    if committed != generated:
        changed = sorted(set(committed) | set(generated))
        raise RuntimeError(
            "Generated Glue expression parser is stale; run "
            f"'uv run python {Path(__file__).name} --write'. Compared: {changed}"
        )
    _event("antlr.check.after", status="clean", files=sorted(generated))


def _write(generated: dict[str, bytes]) -> None:
    _DESTINATION.mkdir(parents=True, exist_ok=True)
    expected = set(generated)
    for path in _DESTINATION.glob("*.py"):
        if path.name != "__init__.py" and path.name not in expected:
            path.unlink()
    for name, content in generated.items():
        (_DESTINATION / name).write_bytes(content)
    _event("antlr.write.after", destination=str(_DESTINATION), files=sorted(generated))


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    lock = json.loads(_LOCK.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="mystack-antlr-") as directory:
        temporary = Path(directory)
        jar = temporary / f"antlr-{lock['version']}-complete.jar"
        output = temporary / "generated"
        output.mkdir()
        _download_jar(lock, jar)
        generated = _generate(lock, output, jar)
    if arguments.check:
        _check(generated)
    else:
        _write(generated)


if __name__ == "__main__":
    main()
