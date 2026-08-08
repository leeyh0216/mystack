"""Opaque EMR marker pagination owned by the application layer.

Official marker contracts:
https://docs.aws.amazon.com/emr/latest/APIReference/API_ListClusters.html
"""

from __future__ import annotations

import base64
import binascii
from typing import TypeVar

from mystack.emr.domain.errors import InvalidClusterStateError

_Item = TypeVar("_Item")


class Paginator:
    def __init__(self, page_size: int) -> None:
        self._page_size = page_size

    def page(self, items: list[_Item], marker: str | None) -> tuple[list[_Item], str | None]:
        offset = self._decode(marker)
        page = items[offset : offset + self._page_size]
        next_offset = offset + len(page)
        next_marker = self._encode(next_offset) if next_offset < len(items) else None
        return page, next_marker

    @staticmethod
    def _encode(offset: int) -> str:
        return base64.urlsafe_b64encode(str(offset).encode()).decode()

    @staticmethod
    def _decode(marker: str | None) -> int:
        if not marker:
            return 0
        try:
            offset = int(base64.urlsafe_b64decode(marker.encode()).decode())
        except (ValueError, UnicodeDecodeError, binascii.Error) as error:
            raise InvalidClusterStateError("Invalid pagination marker") from error
        if offset < 0:
            raise InvalidClusterStateError("Invalid pagination marker")
        return offset
