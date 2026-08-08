"""AWS wire-protocol building blocks shared by Mystack service adapters."""

from mystack.aws_protocol.configuration import (
    ConfigurationError,
    LoadedConfiguration,
    load_configuration,
)
from mystack.aws_protocol.context import AwsRequestContext
from mystack.aws_protocol.diagnostics import DiagnosticsSettings, create_diagnostics_router
from mystack.aws_protocol.dispatcher import OperationDispatcher
from mystack.aws_protocol.endpoint import AwsJsonRpcEndpoint
from mystack.aws_protocol.errors import AwsServiceError
from mystack.aws_protocol.management import ManagementUiSettings
from mystack.aws_protocol.model import AwsServiceModel
from mystack.aws_protocol.operation_registry import OperationFamily, OperationFamilyRegistry
from mystack.aws_protocol.static_ui import HistoryFallbackStaticFiles

__all__ = [
    "AwsJsonRpcEndpoint",
    "AwsRequestContext",
    "AwsServiceError",
    "AwsServiceModel",
    "ConfigurationError",
    "DiagnosticsSettings",
    "HistoryFallbackStaticFiles",
    "LoadedConfiguration",
    "ManagementUiSettings",
    "OperationDispatcher",
    "OperationFamily",
    "OperationFamilyRegistry",
    "create_diagnostics_router",
    "load_configuration",
]
