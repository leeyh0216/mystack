"""Glue application outbound ports.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...
