"""Safe observability for Iceberg optimistic GlueCatalog commits.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking
- https://iceberg.apache.org/docs/1.7.1/reliability/#concurrent-write-operations
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from mystack.aws_protocol.observability import log_event
from mystack.glue.domain import CatalogTable

_LOGGER = logging.getLogger(__name__)


class IcebergCommitObserver:
    """Create an attempt logger only when either table definition identifies Iceberg."""

    def begin(
        self,
        current: CatalogTable,
        candidate_definition: dict[str, Any],
        *,
        expected_version_id: str | None,
        skip_archive: bool,
    ) -> IcebergCommitAttempt | None:
        if not (_is_iceberg(current.definition) or _is_iceberg(candidate_definition)):
            return None
        attempt = IcebergCommitAttempt(
            resource_fingerprint=_fingerprint(
                f"{current.catalog_id}/{current.database_name}/{current.name}"
            ),
            metadata_location_fingerprint=_metadata_location_fingerprint(candidate_definition),
            expected_version_id=expected_version_id,
            current_version_id=current.version_id,
            skip_archive=skip_archive,
        )
        attempt.started()
        return attempt


@dataclass(frozen=True, slots=True)
class IcebergCommitAttempt:
    """Emit commit state transitions without logging catalog payloads or S3 paths."""

    resource_fingerprint: str
    metadata_location_fingerprint: str | None
    expected_version_id: str | None
    current_version_id: str
    skip_archive: bool

    def started(self) -> None:
        self._log(
            logging.INFO,
            "glue.iceberg.commit.begin",
            version_decision="pending",
            side_effect=False,
        )

    def accepted(self, candidate_version_id: str) -> None:
        self._log(
            logging.INFO,
            "glue.iceberg.commit.version.accepted",
            version_decision="accepted",
            candidate_version_id=candidate_version_id,
            side_effect=False,
        )

    def persisting(self, candidate_version_id: str) -> None:
        self._log(
            logging.INFO,
            "glue.iceberg.commit.persist.before",
            candidate_version_id=candidate_version_id,
            side_effect=True,
        )

    def conflicted(self) -> None:
        self._log(
            logging.WARNING,
            "glue.iceberg.commit.conflict",
            version_decision="rejected-stale-version",
            retry_guidance="refresh Glue table VersionId and retry from the new metadata base",
            side_effect=False,
        )

    def succeeded(self, committed_version_id: str) -> None:
        self._log(
            logging.INFO,
            "glue.iceberg.commit.succeeded",
            committed_version_id=committed_version_id,
            side_effect=True,
        )

    def failed(self, error: BaseException) -> None:
        self._log(
            logging.ERROR,
            "glue.iceberg.commit.failed",
            error_type=type(error).__name__,
            fix_hint=(
                "Use the resource and metadata fingerprints to correlate this attempt; "
                "inspect GlueCatalog client changes if VersionId or metadata-location is absent."
            ),
            side_effect=True,
        )

    def _log(self, level: int, event: str, **fields: Any) -> None:
        log_event(
            _LOGGER,
            level,
            event,
            resource_fingerprint=self.resource_fingerprint,
            metadata_location_fingerprint=self.metadata_location_fingerprint,
            expected_version_id=self.expected_version_id,
            current_version_id=self.current_version_id,
            skip_archive=self.skip_archive,
            **fields,
        )


def _is_iceberg(definition: dict[str, Any]) -> bool:
    parameters = definition.get("Parameters")
    if not isinstance(parameters, dict):
        return False
    return str(parameters.get("table_type", "")).casefold() == "iceberg"


def _metadata_location_fingerprint(definition: dict[str, Any]) -> str | None:
    parameters = definition.get("Parameters")
    if not isinstance(parameters, dict):
        return None
    location = parameters.get("metadata_location")
    if not isinstance(location, str) or not location:
        return None
    return _fingerprint(location)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]
