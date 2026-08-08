"""AWS JSON error representation used at the service adapter boundary.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/CommonErrors.html
- https://docs.aws.amazon.com/emr/latest/APIReference/CommonErrors.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class AwsServiceError(Exception):
    code: str
    message: str
    http_status: int = 400
    details: dict[str, Any] = field(default_factory=dict)
    fix_hint: str | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def response_members(self) -> dict[str, Any]:
        return {"__type": self.code, "Message": self.message, **self.details}
