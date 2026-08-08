"""Partition and batch error decisions through the AWS JSON 1.1 boundary.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchGetPartition.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from mystack.glue.application.policies import GlueFaultInjectionPolicy, GlueFaultRule

from test_support.glue_error_harness import GlueCatalogHarness, ToggleFailureStore


@dataclass(frozen=True, slots=True)
class PartitionErrorScenario:
    operation: str
    payload: dict
    message_fragment: str


@pytest.fixture
def catalog() -> GlueCatalogHarness:
    harness = GlueCatalogHarness()
    try:
        yield harness
    finally:
        harness.close()


@pytest.mark.parametrize(
    "scenario",
    (
        PartitionErrorScenario(
            "GetPartition",
            {
                "DatabaseName": "source",
                "TableName": "events",
                "PartitionValues": [],
            },
            "table requires 1",
        ),
        PartitionErrorScenario(
            "DeletePartition",
            {
                "DatabaseName": "source",
                "TableName": "events",
                "PartitionValues": [],
            },
            "table requires 1",
        ),
        PartitionErrorScenario(
            "UpdatePartition",
            {
                "DatabaseName": "source",
                "TableName": "events",
                "PartitionValueList": [],
                "PartitionInput": {"Values": []},
            },
            "table requires 1",
        ),
    ),
    ids=lambda scenario: scenario.operation,
)
def test_partition_value_cardinality_fails_before_item_lookup(
    catalog: GlueCatalogHarness,
    scenario: PartitionErrorScenario,
) -> None:
    catalog.arrange("table")
    before = catalog.durable_state()

    response = catalog.call(scenario.operation, scenario.payload)

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidInputException"
    assert scenario.message_fragment in response.json()["Message"]
    assert catalog.durable_state() == before


def test_protocol_rejects_non_string_partition_value_before_application(
    catalog: GlueCatalogHarness,
) -> None:
    catalog.arrange("table")
    before = catalog.durable_state()

    response = catalog.call(
        "CreatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionInput": {"Values": [20260809]},
        },
    )

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidInputException"
    assert catalog.durable_state() == before


def test_get_partitions_validates_page_segment_and_syntax_before_repository(
    catalog: GlueCatalogHarness,
) -> None:
    invalid_page = catalog.call(
        "GetPartitions",
        {
            "DatabaseName": "missing",
            "TableName": "events",
            "NextToken": "not-a-token",
            "Expression": "[",
        },
    )
    invalid_segment = catalog.call(
        "GetPartitions",
        {
            "DatabaseName": "missing",
            "TableName": "events",
            "Segment": {"SegmentNumber": 2, "TotalSegments": 2},
            "Expression": "[",
        },
    )
    invalid_syntax = catalog.call(
        "GetPartitions",
        {
            "DatabaseName": "missing",
            "TableName": "events",
            "Expression": "[",
        },
    )
    missing_schema = catalog.call(
        "GetPartitions",
        {
            "DatabaseName": "missing",
            "TableName": "events",
            "Expression": "unknown_key = 'value'",
        },
    )

    assert "pagination token" in invalid_page.json()["Message"]
    assert "SegmentNumber" in invalid_segment.json()["Message"]
    assert "partition expression" in invalid_syntax.json()["Message"]
    assert missing_schema.json()["__type"] == "EntityNotFoundException"


def test_update_partition_preserves_omitted_values_and_uses_modeled_collision_error(
    catalog: GlueCatalogHarness,
) -> None:
    catalog.arrange("table")
    _create_partition(catalog, "one")
    _create_partition(catalog, "two")
    catalog.require_success(
        "UpdatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionValueList": ["one"],
            "PartitionInput": {"Parameters": {"revision": "kept-key"}},
        },
    )
    before_collision = catalog.durable_state()

    collision = catalog.call(
        "UpdatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionValueList": ["one"],
            "PartitionInput": {"Values": ["two"]},
        },
    )

    assert collision.status_code == 400
    assert collision.json()["__type"] == "InvalidInputException"
    assert catalog.durable_state() == before_collision
    preserved = catalog.require_success(
        "GetPartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionValues": ["one"],
        },
    )["Partition"]
    assert preserved["Parameters"] == {"revision": "kept-key"}


@pytest.mark.parametrize(
    ("operation", "items"),
    (
        ("BatchCreatePartition", {"PartitionInputList": [{"Values": ["one"]}]}),
        ("BatchGetPartition", {"PartitionsToGet": [{"Values": ["one"]}]}),
        (
            "BatchUpdatePartition",
            {
                "Entries": [
                    {
                        "PartitionValueList": ["one"],
                        "PartitionInput": {"Values": ["one"]},
                    }
                ]
            },
        ),
        ("BatchDeletePartition", {"PartitionsToDelete": [{"Values": ["one"]}]}),
    ),
)
def test_batch_parent_absence_is_an_operation_error(
    catalog: GlueCatalogHarness,
    operation: str,
    items: dict,
) -> None:
    response = catalog.call(
        operation,
        {"DatabaseName": "missing", "TableName": "events", **items},
    )

    assert response.status_code == 400
    assert response.json()["__type"] == "EntityNotFoundException"


def test_batch_create_reports_duplicates_and_invalid_items_in_input_order(
    catalog: GlueCatalogHarness,
) -> None:
    catalog.arrange("table")
    _create_partition(catalog, "existing")

    result = catalog.require_success(
        "BatchCreatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionInputList": [
                {"Values": ["existing"]},
                {"Values": ["new"]},
                {"Values": ["new"]},
                {"Values": []},
            ],
        },
    )

    assert [value["PartitionValues"] for value in result["Errors"]] == [
        ["existing"],
        ["new"],
        [],
    ]
    assert [value["ErrorDetail"]["ErrorCode"] for value in result["Errors"]] == [
        "AlreadyExistsException",
        "AlreadyExistsException",
        "InvalidInputException",
    ]
    assert _partition_values(catalog) == {("existing",), ("new",)}


def test_batch_get_preserves_success_duplicates_and_unprocessed_order(
    catalog: GlueCatalogHarness,
) -> None:
    catalog.arrange("table")
    _create_partition(catalog, "one")

    result = catalog.require_success(
        "BatchGetPartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionsToGet": [
                {"Values": ["one"]},
                {"Values": ["missing"]},
                {"Values": ["one"]},
            ],
        },
    )
    invalid = catalog.call(
        "BatchGetPartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionsToGet": [{"Values": []}, {"Values": ["one"]}],
        },
    )

    assert [value["Values"] for value in result["Partitions"]] == [["one"], ["one"]]
    assert result["UnprocessedKeys"] == [{"Values": ["missing"]}]
    assert invalid.status_code == 400
    assert invalid.json()["__type"] == "InvalidInputException"


def test_batch_update_and_delete_apply_items_sequentially_with_stable_errors(
    catalog: GlueCatalogHarness,
) -> None:
    catalog.arrange("table")
    _create_partition(catalog, "one")
    _create_partition(catalog, "two")
    updated = catalog.require_success(
        "BatchUpdatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "Entries": [
                {
                    "PartitionValueList": ["one"],
                    "PartitionInput": {"Values": ["renamed"]},
                },
                {
                    "PartitionValueList": ["one"],
                    "PartitionInput": {"Values": ["one"]},
                },
                {
                    "PartitionValueList": ["two"],
                    "PartitionInput": {"Values": ["renamed"]},
                },
                {
                    "PartitionValueList": ["missing"],
                    "PartitionInput": {"Values": ["missing"]},
                },
                {
                    "PartitionValueList": ["two"],
                    "PartitionInput": {"Parameters": {"revision": "last"}},
                },
            ],
        },
    )

    assert [value["PartitionValueList"] for value in updated["Errors"]] == [
        ["one"],
        ["two"],
        ["missing"],
    ]
    assert [value["ErrorDetail"]["ErrorCode"] for value in updated["Errors"]] == [
        "EntityNotFoundException",
        "InvalidInputException",
        "EntityNotFoundException",
    ]
    deleted = catalog.require_success(
        "BatchDeletePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionsToDelete": [
                {"Values": ["renamed"]},
                {"Values": ["renamed"]},
                {"Values": ["missing"]},
                {"Values": []},
            ],
        },
    )
    assert [value["PartitionValues"] for value in deleted["Errors"]] == [
        ["renamed"],
        ["missing"],
        [],
    ]
    assert [value["ErrorDetail"]["ErrorCode"] for value in deleted["Errors"]] == [
        "EntityNotFoundException",
        "EntityNotFoundException",
        "InvalidInputException",
    ]
    remaining = catalog.require_success(
        "GetPartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionValues": ["two"],
        },
    )["Partition"]
    assert remaining["Parameters"] == {"revision": "last"}


def test_batch_persistence_failure_keeps_prior_commits_and_rolls_back_failed_item() -> None:
    store = ToggleFailureStore()
    catalog = GlueCatalogHarness(store)
    try:
        catalog.arrange("table")
        store.fail_on_attempt = store.save_attempts + 2

        response = catalog.call(
            "BatchCreatePartition",
            {
                "DatabaseName": "source",
                "TableName": "events",
                "PartitionInputList": [
                    {"Values": ["committed"]},
                    {"Values": ["rolled-back"]},
                    {"Values": ["not-attempted"]},
                ],
            },
        )

        assert response.status_code == 500
        assert response.json()["__type"] == "InternalServiceException"
        assert _partition_values(catalog) == {("committed",)}
    finally:
        catalog.close()


def test_configured_batch_fault_precedes_parent_lookup_and_mutation() -> None:
    policy = GlueFaultInjectionPolicy(
        enabled=True,
        rules=(
            GlueFaultRule(
                "timeout-batch-create",
                "BatchCreatePartition",
                "OperationTimeoutException",
                "configured partition timeout",
            ),
        ),
    )
    catalog = GlueCatalogHarness(fault_injection=policy)
    try:
        before = catalog.durable_state()

        response = catalog.call(
            "BatchCreatePartition",
            {
                "DatabaseName": "missing",
                "TableName": "events",
                "PartitionInputList": [{"Values": ["one"]}],
            },
        )

        assert response.status_code == 400
        assert response.json()["__type"] == "OperationTimeoutException"
        assert catalog.durable_state() == before
    finally:
        catalog.close()


def _create_partition(catalog: GlueCatalogHarness, value: str) -> None:
    catalog.require_success(
        "CreatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionInput": {"Values": [value]},
        },
    )


def _partition_values(catalog: GlueCatalogHarness) -> set[tuple[str, ...]]:
    return {key[3] for key in catalog.durable_state().partitions}
