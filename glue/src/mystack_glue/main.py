"""File-driven Glue Data Catalog entry point.

Configuration reference: https://docs.docker.com/reference/compose-file/configs/
"""

import argparse

import uvicorn
from mystack_aws_protocol import load_configuration

from .app import create_app
from .config import GlueSettings


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the Mystack Glue Data Catalog emulator")
    parser.add_argument("--config", help="Path to the versioned Mystack YAML configuration")
    parser.add_argument("--host", help="Override glue.listen.host")
    parser.add_argument("--port", type=int, help="Override glue.listen.port")
    args = parser.parse_args()

    loaded = load_configuration(args.config)
    settings = GlueSettings.from_configuration(loaded)
    uvicorn.run(
        create_app(settings, configuration=loaded),
        host=args.host or settings.listen_host,
        port=args.port or settings.listen_port,
    )
