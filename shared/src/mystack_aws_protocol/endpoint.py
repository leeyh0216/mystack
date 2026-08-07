"""AWS JSON 1.1 HTTP controller.

Protocol metadata is sourced from official botocore models:
https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .context import AwsRequestContext
from .dispatcher import OperationDispatcher
from .errors import AwsServiceError
from .model import AwsServiceModel
from .observability import log_event, payload_fingerprint

_LOGGER = logging.getLogger(__name__)

_CREDENTIAL_SCOPE = re.compile(
    r"Credential=[^/]+/(?P<date>\d{8})/(?P<region>[^/]+)/(?P<service>[^/]+)/aws4_request"
)


class AwsJsonRpcEndpoint:
    """FastAPI-neutral request handler for AWS JSON 1.1 service endpoints."""

    def __init__(
        self,
        model: AwsServiceModel,
        dispatcher: OperationDispatcher,
        *,
        default_region: str,
        account_id: str,
    ) -> None:
        self._model = model
        self._dispatcher = dispatcher
        self._default_region = default_region
        self._account_id = account_id

    async def __call__(self, request: Request) -> Response:
        request_id = str(uuid.uuid4())
        started = time.monotonic()
        raw_body = await request.body()
        log_event(
            _LOGGER,
            logging.INFO,
            "controller.request.received",
            request_id=request_id,
            service=self._model.metadata.service_name,
            target=request.headers.get("x-amz-target", ""),
            method=request.method,
            path=request.url.path,
            payload_bytes=len(raw_body),
            payload_fingerprint=payload_fingerprint(raw_body),
            model_fingerprint=self._model.fingerprint,
            api_version=self._model.metadata.api_version,
        )
        try:
            operation_name = self._operation_name(request.headers)
            operation = self._model.operation(operation_name)
            payload = self._payload(raw_body)
            self._model.validate(operation, payload)
            context = self._context(request, request_id, operation_name)
            result = await self._dispatcher.dispatch(operation_name, payload, context)
            response = self._success(result, request_id)
            log_event(
                _LOGGER,
                logging.INFO,
                "controller.request.completed",
                request_id=request_id,
                service=self._model.metadata.service_name,
                operation=operation_name,
                status_code=response.status_code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
            return response
        except AwsServiceError as error:
            log_event(
                _LOGGER,
                logging.WARNING,
                "controller.request.service_error",
                request_id=request_id,
                service=self._model.metadata.service_name,
                error_code=error.code,
                status_code=error.http_status,
                model_fingerprint=self._model.fingerprint,
                fix_hint=error.fix_hint,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
            return self._error(error, request_id)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "controller.request.unhandled_error",
                request_id=request_id,
                service=self._model.metadata.service_name,
                model_fingerprint=self._model.fingerprint,
                fix_hint=(
                    "Inspect this traceback; an unmodeled exception crossed "
                    "the controller boundary."
                ),
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                exc_info=True,
            )
            error = AwsServiceError(
                "InternalServiceException",
                "An internal service error occurred.",
                http_status=500,
            )
            return self._error(error, request_id)

    def _operation_name(self, headers: Mapping[str, str]) -> str:
        target = headers.get("x-amz-target", "")
        prefix = f"{self._model.metadata.target_prefix}."
        if not target.startswith(prefix) or len(target) == len(prefix):
            raise AwsServiceError(
                "UnknownOperationException",
                "The requested operation is not recognized by this service.",
                http_status=404,
            )
        return target.removeprefix(prefix)

    def _payload(self, raw: bytes) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            payload: Any = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AwsServiceError(
                "SerializationException",
                "Could not parse request body into JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise AwsServiceError("SerializationException", "Request body must be a JSON object.")
        return payload

    def _context(
        self,
        request: Request,
        request_id: str,
        operation: str,
    ) -> AwsRequestContext:
        authorization = request.headers.get("authorization", "")
        match = _CREDENTIAL_SCOPE.search(authorization)
        region = match.group("region") if match else self._default_region
        return AwsRequestContext(
            request_id=request_id,
            service=self._model.metadata.service_name,
            operation=operation,
            region=region,
            account_id=self._account_id,
            headers=dict(request.headers),
        )

    @staticmethod
    def _headers(request_id: str) -> dict[str, str]:
        return {
            "content-type": "application/x-amz-json-1.1",
            "x-amzn-requestid": request_id,
        }

    def _success(self, result: Mapping[str, Any], request_id: str) -> JSONResponse:
        return JSONResponse(dict(result), headers=self._headers(request_id))

    def _error(self, error: AwsServiceError, request_id: str) -> JSONResponse:
        headers = self._headers(request_id)
        headers["x-amzn-errortype"] = error.code
        return JSONResponse(
            error.response_members(),
            status_code=error.http_status,
            headers=headers,
        )
