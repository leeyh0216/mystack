"""All implemented Glue operations through the public Proxy endpoint.

Official endpoint configuration reference:
https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from mystack.glue.adapters.inbound.aws_operations import IMPLEMENTED_GLUE_OPERATIONS

from test_support.compatibility import compatibility_evidence
from test_support.compatibility_profiles import BOTO3_BOTOCORE_PUBLIC_PROXY
from test_support.glue_catalog import exercise_all_glue_catalog_operations


@pytest.mark.e2e
@compatibility_evidence(
    BOTO3_BOTOCORE_PUBLIC_PROXY,
    scenario_ids=("glue-operations-through-public-proxy",),
    operations={"glue": tuple(sorted(IMPLEMENTED_GLUE_OPERATIONS))},
    capabilities=("public-proxy", "catalog-operation-boundary"),
)
def test_all_implemented_glue_operations_through_public_proxy(
    aws_clients: dict[str, Any],
) -> None:
    namespace = f"proxy_{uuid.uuid4().hex}"
    exercise_all_glue_catalog_operations(aws_clients["glue"], namespace)
