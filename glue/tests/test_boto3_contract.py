"""Black-box boto3 contracts for every implemented Glue Data Catalog operation.

API reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

import pytest

from test_support.glue_catalog import exercise_all_glue_catalog_operations


@pytest.mark.contract
def test_all_implemented_glue_operations_through_service_boundary(glue_client) -> None:
    exercise_all_glue_catalog_operations(glue_client, "contract")
