"""Export hash-locked container requirements and detect lockfile drift.

The command and hash format are defined by the official uv export interface:
https://docs.astral.sh/uv/reference/cli/#uv-export
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
COMPONENTS = ("proxy", "emr", "glue")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing when generated requirements differ.",
    )
    args = parser.parse_args()
    failures: list[str] = []
    destination = ROOT / "requirements"
    destination.mkdir(exist_ok=True)

    for component in COMPONENTS:
        command = [
            "uv",
            "export",
            "--frozen",
            "--package",
            f"mystack-{component}",
            "--no-dev",
            "--no-emit-project",
            "--no-emit-workspace",
            "--format",
            "requirements.txt",
        ]
        generated = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        target = destination / f"{component}.txt"
        if args.check:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != generated:
                failures.append(str(target.relative_to(ROOT)))
        else:
            target.write_text(generated, encoding="utf-8")
            print(f"requirements.exported component={component} path={target.relative_to(ROOT)}")

    if failures:
        joined = ", ".join(failures)
        raise SystemExit(
            f"container requirement locks are stale: {joined}; run `make requirements`"
        )


if __name__ == "__main__":
    main()
