"""Static React application adapter with safe history-route fallback.

Starlette's packaged static-file contract provides conditional and range responses:
https://www.starlette.io/staticfiles/

Only extensionless browser navigation falls back to ``index.html``. Missing assets and JSON API
requests retain their ordinary 404 behavior, so a protocol mismatch is not hidden by the SPA.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class HistoryFallbackStaticFiles(StaticFiles):
    """Serve a built UI and resolve extensionless history routes to its entry document."""

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or not _is_history_navigation(path, scope):
                raise
        else:
            if response.status_code != 404 or not _is_history_navigation(path, scope):
                return response
        return await super().get_response("index.html", scope)


def _is_history_navigation(path: str, scope: dict[str, Any]) -> bool:
    if scope.get("method") not in {"GET", "HEAD"} or PurePosixPath(path).suffix:
        return False
    headers = {key.lower(): value for key, value in scope.get("headers", ())}
    accept = headers.get(b"accept", b"").lower()
    return not accept or b"text/html" in accept or b"*/*" in accept
