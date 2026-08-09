"""Immutable partition-expression syntax and schema values.

The supported grammar and partition-key types come from the AWS Glue
``GetPartitions`` contract:
https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias


class TokenKind(Enum):
    EQ = auto()
    NE = auto()
    GT = auto()
    GE = auto()
    LT = auto()
    LE = auto()
    AND = auto()
    OR = auto()


@dataclass(frozen=True, slots=True)
class Literal:
    value: str | None


@dataclass(frozen=True, slots=True)
class Comparison:
    field: str
    operator: TokenKind
    value: Literal


@dataclass(frozen=True, slots=True)
class Logical:
    operator: TokenKind
    left: Expression
    right: Expression


@dataclass(frozen=True, slots=True)
class Negation:
    operand: Expression


@dataclass(frozen=True, slots=True)
class Membership:
    field: str
    values: tuple[Literal, ...]
    negated: bool


@dataclass(frozen=True, slots=True)
class Range:
    field: str
    lower: Literal
    upper: Literal
    negated: bool


@dataclass(frozen=True, slots=True)
class Pattern:
    field: str
    value: Literal
    negated: bool


@dataclass(frozen=True, slots=True)
class NullCheck:
    field: str
    negated: bool


Expression: TypeAlias = Comparison | Logical | Negation | Membership | Range | Pattern | NullCheck


@dataclass(frozen=True, slots=True)
class PartitionKey:
    name: str
    type_name: str


@dataclass(frozen=True, slots=True)
class PartitionExpressionPolicy:
    max_length: int
    max_tokens: int
    supported_key_types: tuple[str, ...]
    fallback_max_candidates: int = 1_000

    def __post_init__(self) -> None:
        if self.fallback_max_candidates <= 0:
            raise ValueError("fallback_max_candidates must be positive")
