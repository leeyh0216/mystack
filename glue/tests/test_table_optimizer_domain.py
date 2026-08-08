"""Managed Glue Iceberg table-optimizer domain contracts.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
- https://docs.aws.amazon.com/glue/latest/dg/compaction-management.html
- https://docs.aws.amazon.com/glue/latest/dg/optimizer-notes.html
"""

from __future__ import annotations

import pytest
from mystack.glue.domain import (
    InvalidInputError,
    TableOptimizer,
    TableOptimizerConfiguration,
    TableOptimizerEventType,
    TableOptimizerType,
)


def _configuration(
    optimizer_type: TableOptimizerType,
    document: dict | None = None,
) -> TableOptimizerConfiguration:
    return TableOptimizerConfiguration.parse(
        optimizer_type,
        document or {},
        table_location="s3://warehouse/db/table",
    )


def _optimizer(
    optimizer_type: TableOptimizerType = TableOptimizerType.COMPACTION,
) -> TableOptimizer:
    return TableOptimizer.create(
        catalog_id="account",
        database_name="db",
        table_name="table",
        optimizer_type=optimizer_type,
        configuration=_configuration(optimizer_type),
        now=10.0,
        initial_delay_seconds=5.0,
    )


def test_documented_defaults_are_normalized_per_optimizer_type() -> None:
    compaction = _configuration(TableOptimizerType.COMPACTION).document
    retention = _configuration(TableOptimizerType.RETENTION).document
    orphan = _configuration(TableOptimizerType.ORPHAN_FILE_DELETION).document

    assert compaction == {
        "enabled": True,
        "compactionConfiguration": {
            "icebergConfiguration": {
                "strategy": "binpack",
                "minInputFiles": 100,
                "deleteFileThreshold": 1,
            }
        },
    }
    assert retention["retentionConfiguration"]["icebergConfiguration"] == {
        "snapshotRetentionPeriodInDays": 5,
        "numberOfSnapshotsToRetain": 1,
        "cleanExpiredFiles": True,
        "runRateInHours": 24,
    }
    assert orphan["orphanFileDeletionConfiguration"]["icebergConfiguration"] == {
        "orphanFileRetentionPeriodInDays": 3,
        "location": "s3://warehouse/db/table",
        "runRateInHours": 24,
    }

    root_location = TableOptimizerConfiguration.parse(
        TableOptimizerType.ORPHAN_FILE_DELETION,
        {},
        table_location="s3://warehouse",
    ).document
    assert (
        root_location["orphanFileDeletionConfiguration"]["icebergConfiguration"]["location"]
        == "s3://warehouse"
    )


@pytest.mark.parametrize(
    "document, message",
    [
        ({"enabled": "true"}, "enabled must be a Boolean"),
        (
            {"retentionConfiguration": {"icebergConfiguration": {"runRateInHours": 2}}},
            "between 3 and 168",
        ),
        (
            {
                "orphanFileDeletionConfiguration": {
                    "icebergConfiguration": {"location": "s3://warehouse/db/table-copy"}
                }
            },
            "inside the table location",
        ),
    ],
)
def test_invalid_configuration_is_rejected_without_repository_access(
    document: dict,
    message: str,
) -> None:
    optimizer_type = (
        TableOptimizerType.RETENTION
        if "retentionConfiguration" in document
        else TableOptimizerType.ORPHAN_FILE_DELETION
        if "orphanFileDeletionConfiguration" in document
        else TableOptimizerType.COMPACTION
    )

    with pytest.raises(InvalidInputError, match=message):
        _configuration(optimizer_type, document)


def test_run_lifecycle_records_metrics_and_schedules_the_next_run() -> None:
    value = _optimizer().claim("run-1", 15.0, history_limit=10)
    value = value.mark_in_progress("run-1")
    value = value.complete_run(
        "run-1",
        now=20.0,
        metrics={"NumberOfFilesCompacted": "2"},
        compaction_interval_seconds=1800.0,
    )

    assert value.last_run is not None
    assert value.last_run.event_type is TableOptimizerEventType.COMPLETED
    assert value.last_run.metrics == {"NumberOfFilesCompacted": "2"}
    assert value.next_run_time == 1820.0
    assert value.consecutive_failures == 0


def test_four_consecutive_compaction_failures_suspend_the_optimizer() -> None:
    value = _optimizer()
    now = 15.0
    for index in range(4):
        value = value.claim(f"run-{index}", now, history_limit=10)
        value = value.fail_run(
            f"run-{index}",
            now=now + 1.0,
            error="injected failure",
            compaction_interval_seconds=1.0,
            compaction_failure_limit=4,
        )
        now += 2.0

    assert value.configuration.enabled is False
    assert value.next_run_time is None
    assert value.consecutive_failures == 4

    revised = value.revise(
        _configuration(TableOptimizerType.COMPACTION),
        now=30.0,
        initial_delay_seconds=5.0,
    )

    assert revised.configuration.enabled is True
    assert revised.consecutive_failures == 0
    assert revised.next_run_time == 35.0
