"""File-driven EMR emulator entry point.

Configuration reference: https://docs.docker.com/reference/compose-file/configs/
"""

import argparse

import uvicorn
from mystack_aws_protocol import load_configuration

from .app import create_app
from .config import EmrSettings

app = create_app()


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the Mystack EMR emulator")
    parser.add_argument("--config", help="Path to the versioned Mystack YAML configuration")
    parser.add_argument("--host", help="Override emr.listen.host")
    parser.add_argument("--port", type=int, help="Override emr.listen.port")
    args = parser.parse_args()

    loaded = load_configuration(args.config)
    settings = EmrSettings.from_configuration(loaded)
    uvicorn.run(
        create_app(settings, configuration=loaded),
        host=args.host or settings.listen_host,
        port=args.port or settings.listen_port,
    )
