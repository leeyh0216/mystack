"""Stable application values shared by optimizer use cases and outbound ports.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mystack.glue.domain import TableOptimizerKey, TableOptimizerType


@dataclass(frozen=True, slots=True)
class TableOptimizerWork:
    key: TableOptimizerKey
    run_id: str
    configuration_revision: int
    configuration: dict[str, Any]
    table_location: str
    optimizer_create_time: float

    @property
    def optimizer_type(self) -> TableOptimizerType:
        return TableOptimizerType(self.key[3])
