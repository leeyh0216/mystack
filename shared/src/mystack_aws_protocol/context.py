"""Request context derived from AWS SigV4 metadata.

Reference: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class AwsRequestContext:
    request_id: str
    service: str
    operation: str
    region: str
    account_id: str
    headers: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
