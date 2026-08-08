"""Serve the packaged, dependency-free Mystack management console assets.

Visual vocabulary reference: https://aws.amazon.com/console/
FastAPI HTML response reference: https://fastapi.tiangolo.com/advanced/custom-response/
"""

from importlib.resources import files

from fastapi.responses import HTMLResponse, Response

_ASSETS = {
    "console.css": "text/css; charset=utf-8",
    "console.js": "text/javascript; charset=utf-8",
    "api.js": "text/javascript; charset=utf-8",
    "emr.js": "text/javascript; charset=utf-8",
    "glue.js": "text/javascript; charset=utf-8",
}


def console_response(*, refresh_interval_seconds: float, log_buffer_bytes: int) -> HTMLResponse:
    document = files("mystack.proxy").joinpath("static/console.html").read_text(encoding="utf-8")
    document = document.replace(
        "__MYSTACK_REFRESH_INTERVAL_MS__",
        str(round(refresh_interval_seconds * 1000)),
    )
    document = document.replace("__MYSTACK_LOG_BUFFER_BYTES__", str(log_buffer_bytes))
    return HTMLResponse(document)


def console_asset_response(asset_name: str) -> Response:
    """Return an allow-listed package asset without resolving a caller-controlled path."""

    media_type = _ASSETS.get(asset_name)
    if media_type is None:
        return Response(status_code=404)
    content = files("mystack.proxy").joinpath("static", asset_name).read_bytes()
    return Response(
        content,
        media_type=media_type,
        headers={"Cache-Control": "no-cache"},
    )
