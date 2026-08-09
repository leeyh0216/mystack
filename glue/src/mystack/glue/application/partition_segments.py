"""Pure, stable Glue partition segment allocation.

The implementation mirrors the request-level semantics used by ``GetPartitions`` and is shared
with the SQLite projection writer so persisted segment assignments cannot drift from application
filtering.

Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

from __future__ import annotations

import hashlib


def stable_partition_segment(values: tuple[str, ...], total_segments: int) -> int:
    """Return the deterministic segment number for one ordered partition-value tuple."""

    digest = hashlib.sha256("\0".join(values).encode()).digest()
    return int.from_bytes(digest[:8], "big") % total_segments
