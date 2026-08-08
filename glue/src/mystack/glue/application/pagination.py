"""Glue pagination token policy shared by focused query handlers.

Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetTables.html
"""

from __future__ import annotations

import base64
import binascii
from typing import TypeVar

from mystack.glue.domain import InvalidInputError

_Item = TypeVar("_Item")


class Paginator:
    def __init__(self, maximum_page_size: int) -> None:
        self._maximum_page_size = maximum_page_size

    def page(
        self,
        values: list[_Item],
        token: str | None,
        requested_size: int | None,
    ) -> tuple[list[_Item], str | None]:
        offset = _decode_token(token)
        size = min(requested_size or self._maximum_page_size, self._maximum_page_size)
        if size <= 0:
            raise InvalidInputError("MaxResults must be positive")
        page = values[offset : offset + size]
        next_offset = offset + len(page)
        return page, _encode_token(next_offset) if next_offset < len(values) else None


def _encode_token(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_token(token: str | None) -> int:
    if not token:
        return 0
    try:
        value = int(base64.urlsafe_b64decode(token.encode()).decode())
        if value < 0:
            raise ValueError
        return value
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidInputError("Invalid pagination token") from error
