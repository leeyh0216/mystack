"""Read one scalar from the effective Mystack configuration.

Configuration mount reference: https://docs.docker.com/reference/compose-file/configs/
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from mystack_aws_protocol import load_configuration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Dot-separated configuration path")
    parser.add_argument("--config", help="Configuration file path")
    args = parser.parse_args()
    value: Any = load_configuration(args.config).document
    for segment in args.path.split("."):
        if not isinstance(value, dict) or segment not in value:
            raise SystemExit(f"Configuration path does not exist: {args.path}")
        value = value[segment]
    if isinstance(value, dict | list):
        print(json.dumps(value, separators=(",", ":"), sort_keys=True))
    elif value is None:
        print("null")
    else:
        print(str(value).lower() if isinstance(value, bool) else value)


if __name__ == "__main__":
    main()
