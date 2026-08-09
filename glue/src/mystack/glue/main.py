"""File-driven Glue Data Catalog entry point.

Configuration reference: https://docs.docker.com/reference/compose-file/configs/
"""

import argparse
import json

import uvicorn
from mystack.aws_protocol import load_configuration
from mystack.glue.app import create_app, verify_sqlite_runtime
from mystack.glue.config import GlueSettings


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the Mystack Glue Data Catalog emulator")
    parser.add_argument("--config", help="Path to the versioned Mystack YAML configuration")
    parser.add_argument("--host", help="Override glue.listen.host")
    parser.add_argument("--port", type=int, help="Override glue.listen.port")
    parser.add_argument(
        "--verify-sqlite-runtime",
        action="store_true",
        help="Validate the configured SQLite runtime and exit without serving HTTP",
    )
    args = parser.parse_args()

    loaded = load_configuration(args.config)
    settings = GlueSettings.from_configuration(loaded)
    if args.verify_sqlite_runtime:
        print(json.dumps(verify_sqlite_runtime(settings), sort_keys=True))
        return
    uvicorn.run(
        create_app(settings, configuration=loaded),
        host=args.host or settings.listen_host,
        port=args.port or settings.listen_port,
    )
