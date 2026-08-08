"""Serve the packaged, dependency-free Mystack management console.

Visual vocabulary reference: https://aws.amazon.com/console/
FastAPI HTML response reference: https://fastapi.tiangolo.com/advanced/custom-response/
"""

from importlib.resources import files

from fastapi.responses import HTMLResponse


def console_response() -> HTMLResponse:
    document = files("mystack.proxy").joinpath("static/console.html").read_text(encoding="utf-8")
    return HTMLResponse(document)
