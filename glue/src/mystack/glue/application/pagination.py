"""Glue pagination token policy shared by focused query handlers.

Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetTables.html
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from typing import TypeVar

from mystack.glue.application.catalog_query_models import SeekCursor
from mystack.glue.domain import InvalidInputError

_Item = TypeVar("_Item")


@dataclass(frozen=True, slots=True)
class PageRequest:
    """A validated pagination request applied only after input checks complete."""

    offset: int
    size: int

    def apply(self, values: list[_Item]) -> tuple[list[_Item], str | None]:
        page = values[self.offset : self.offset + self.size]
        next_offset = self.offset + len(page)
        return page, _encode_token(next_offset) if next_offset < len(values) else None


@dataclass(frozen=True, slots=True)
class KeysetPageRequest:
    """Validated page size and a context-bound opaque seek cursor.

    Token structure is validated before any Catalog lookup so malformed ``NextToken`` keeps the
    established Glue error precedence. Context validation happens once the use case has parsed
    its expression and resolved its parent resource.
    """

    size: int
    cursor: SeekCursor | None
    token_context: str | None

    def bind(self, context: str) -> KeysetPageRequest:
        if self.token_context is not None and not hmac.compare_digest(self.token_context, context):
            raise InvalidInputError("Pagination token does not match this request")
        return replace(self, token_context=context)


class Paginator:
    def __init__(self, maximum_page_size: int) -> None:
        self._maximum_page_size = maximum_page_size

    def page(
        self,
        values: list[_Item],
        token: str | None,
        requested_size: int | None,
    ) -> tuple[list[_Item], str | None]:
        return self.prepare(token, requested_size).apply(values)

    def prepare(self, token: str | None, requested_size: int | None) -> PageRequest:
        """Validate client-controlled paging before a repository read."""

        offset = _decode_token(token)
        size = min(requested_size or self._maximum_page_size, self._maximum_page_size)
        if size <= 0:
            raise InvalidInputError("MaxResults must be positive")
        return PageRequest(offset, size)

    def prepare_keyset(
        self,
        token: str | None,
        requested_size: int | None,
    ) -> KeysetPageRequest:
        """Validate one opaque seek token without reading application state."""

        size = min(requested_size or self._maximum_page_size, self._maximum_page_size)
        if size <= 0:
            raise InvalidInputError("MaxResults must be positive")
        if not token:
            return KeysetPageRequest(size=size, cursor=None, token_context=None)
        context, cursor = _decode_keyset_token(token)
        return KeysetPageRequest(size=size, cursor=cursor, token_context=context)

    @staticmethod
    def context(*parts: object) -> str:
        """Return a value-safe request-scope fingerprint for a token.

        The fingerprint is never logged. It stops a valid token for one Catalog path, expression,
        or segment from being replayed against another one; it is not an authorization mechanism.
        """

        encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def complete_keyset(
        request: KeysetPageRequest,
        next_cursor: SeekCursor | None,
    ) -> str | None:
        if next_cursor is None:
            return None
        if request.token_context is None:
            raise RuntimeError("Keyset page request must be bound before issuing a continuation")
        return _encode_keyset_token(request.token_context, next_cursor)


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


def _encode_keyset_token(context: str, cursor: SeekCursor) -> str:
    document = {
        "v": 1,
        "c": context,
        "i": cursor.identifier,
    }
    payload = json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_keyset_token(token: str) -> tuple[str, SeekCursor]:
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict) or set(document) != {"v", "c", "i"}:
            raise ValueError
        if document["v"] != 1 or not isinstance(document["c"], str):
            raise ValueError
        if not isinstance(document["i"], int):
            raise ValueError
        if isinstance(document["i"], bool) or document["i"] <= 0:
            raise ValueError
        if len(document["c"]) != 64:
            raise ValueError
        return document["c"], SeekCursor(document["i"])
    except (
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise InvalidInputError("Invalid pagination token") from error
