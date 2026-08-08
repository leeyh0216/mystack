"""Framework-free application policy values supplied by composition roots.

Glue exception reference:
https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlueFaultRule:
    rule_id: str
    operation: str
    error_code: str
    message: str


@dataclass(frozen=True, slots=True)
class GlueFaultInjectionPolicy:
    enabled: bool
    rules: tuple[GlueFaultRule, ...]

    @classmethod
    def disabled(cls) -> GlueFaultInjectionPolicy:
        return cls(enabled=False, rules=())
