"""Mutation tests for the machine-readable Glue error catalog compiler.

Official model source:
https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

from __future__ import annotations

import copy

import pytest

from scripts.glue_error_contracts import DEFAULT_CATALOG, _load, _validate


def test_committed_glue_error_catalog_is_complete_and_modeled() -> None:
    _validate(_load(DEFAULT_CATALOG))


def test_glue_error_catalog_rejects_operation_and_authorization_drift() -> None:
    missing_operation = _load(DEFAULT_CATALOG)
    missing_operation["operations"].pop("GetTable")
    with pytest.raises(ValueError, match="operation coverage drift"):
        _validate(missing_operation)

    forbidden = copy.deepcopy(_load(DEFAULT_CATALOG))
    forbidden["conditions"]["input.value_invalid"]["error_code"] = "AccessDeniedException"
    with pytest.raises(ValueError, match="Authorization error is forbidden"):
        _validate(forbidden)


def test_glue_error_catalog_rejects_precedence_drift() -> None:
    document = _load(DEFAULT_CATALOG)
    conditions = document["operations"]["UpdateTable"]
    conditions[1], conditions[-1] = conditions[-1], conditions[1]

    with pytest.raises(ValueError, match="violate precedence"):
        _validate(document)
