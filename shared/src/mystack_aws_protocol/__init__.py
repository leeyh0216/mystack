"""AWS wire-protocol building blocks shared by Mystack service adapters."""

from .configuration import ConfigurationError, LoadedConfiguration, load_configuration
from .context import AwsRequestContext
from .diagnostics import DiagnosticsSettings, create_diagnostics_router
from .dispatcher import OperationDispatcher
from .endpoint import AwsJsonRpcEndpoint
from .errors import AwsServiceError
from .model import AwsServiceModel

__all__ = [
    "AwsJsonRpcEndpoint",
    "AwsRequestContext",
    "AwsServiceError",
    "AwsServiceModel",
    "ConfigurationError",
    "DiagnosticsSettings",
    "LoadedConfiguration",
    "OperationDispatcher",
    "create_diagnostics_router",
    "load_configuration",
]
