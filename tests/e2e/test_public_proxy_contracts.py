"""All implemented Glue operations through the public Proxy endpoint.

Official endpoint configuration reference:
https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from test_support.glue_catalog import exercise_all_glue_catalog_operations


@pytest.mark.e2e
def test_all_implemented_glue_operations_through_public_proxy(
    aws_clients: dict[str, Any],
) -> None:
    namespace = f"proxy_{uuid.uuid4().hex}"
    exercise_all_glue_catalog_operations(aws_clients["glue"], namespace)
