"""File-driven Proxy process entry point.

References:
- https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
- https://docs.docker.com/reference/compose-file/configs/
"""

import argparse

import uvicorn
from mystack.aws_protocol import load_configuration
from mystack.proxy.app import create_app
from mystack.proxy.config import ProxySettings


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the Mystack AWS routing proxy")
    parser.add_argument("--config", help="Path to the versioned Mystack YAML configuration")
    parser.add_argument("--host", help="Override proxy.listen.host")
    parser.add_argument("--port", type=int, help="Override proxy.listen.port")
    args = parser.parse_args()

    loaded = load_configuration(args.config)
    settings = ProxySettings.from_configuration(loaded)
    uvicorn.run(
        create_app(settings, configuration=loaded),
        host=args.host or settings.listen_host,
        port=args.port or settings.listen_port,
    )
