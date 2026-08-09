"""Private stable SQLite keys for partition paging and segmented reads."""

from __future__ import annotations

from mystack.glue.application.partition_segments import stable_partition_segment

_MAX_PARTITION_SEGMENTS = 10


def partition_order_key(values: tuple[str, ...]) -> bytes:
    """Encode a fixed-arity string tuple with Python-compatible lexicographic byte ordering.

    UTF-8 byte ordering preserves Unicode code-point ordering. ``NUL`` is escaped and a doubled
    NUL terminates each value, so prefix values retain their ordinary Python string ordering.
    """

    encoded = bytearray()
    for value in values:
        raw = value.encode("utf-8", "surrogatepass")
        encoded.extend(raw.replace(b"\x00", b"\x00\xff"))
        encoded.extend(b"\x00\x00")
    return bytes(encoded)


def partition_segment_rows(
    partition_id: int,
    table_id: int,
    values: tuple[str, ...],
) -> tuple[tuple[int, int, int, int], ...]:
    """Persist all supported segment allocations for an immutable value tuple."""

    return tuple(
        (
            partition_id,
            table_id,
            total_segments,
            stable_partition_segment(values, total_segments),
        )
        for total_segments in range(1, _MAX_PARTITION_SEGMENTS + 1)
    )
