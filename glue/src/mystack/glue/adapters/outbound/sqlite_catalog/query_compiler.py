"""Compile a bound Glue partition AST to parameterized SQLite predicate fragments.

The compiler receives an already parsed/bound AST. It never parses request text and substitutes
only trusted ordinal-derived aliases into SQL structure; identifiers and literal values are bound
parameters.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://www.sqlite.org/lang_expr.html
"""

from __future__ import annotations

from dataclasses import dataclass

from mystack.glue.adapters.outbound.sqlite_catalog.projection import PartitionValueProjector
from mystack.glue.application.partition_expression.model import (
    Comparison,
    Expression,
    Literal,
    Logical,
    Membership,
    Negation,
    NullCheck,
    PartitionKey,
    Pattern,
    Range,
    TokenKind,
)
from mystack.glue.application.partition_expression.service import CompiledPartitionExpression
from mystack.glue.application.partition_expression.value_codec import PartitionValueError


class UnsupportedPartitionSqlExpression(RuntimeError):
    """A future AST node needs the documented bounded evaluator fallback."""


@dataclass(frozen=True, slots=True)
class ProjectionRequirement:
    ordinal: int
    type_name: str
    type_family: str


@dataclass(frozen=True, slots=True)
class SqlitePartitionPredicate:
    joins: tuple[str, ...]
    predicate_sql: str
    parameters: tuple[object, ...]
    projections: tuple[ProjectionRequirement, ...]


class SqlitePartitionQueryCompiler:
    """Keep AST semantics in application and SQLite syntax generation in the outbound adapter."""

    def __init__(self, projector: PartitionValueProjector | None = None) -> None:
        self._projector = projector or PartitionValueProjector()

    def compile(self, bound: CompiledPartitionExpression) -> SqlitePartitionPredicate:
        if bound.expression is None:
            return SqlitePartitionPredicate((), "1", (), ())
        state = _CompilationState(bound.keys, self._projector)
        predicate = state.expression(bound.expression)
        return SqlitePartitionPredicate(
            joins=tuple(state.joins),
            predicate_sql=predicate,
            parameters=tuple(state.parameters),
            projections=tuple(state.projections.values()),
        )


class _CompilationState:
    def __init__(
        self,
        keys: tuple[PartitionKey, ...],
        projector: PartitionValueProjector,
    ) -> None:
        self._projector = projector
        self._fields: dict[str, tuple[int, PartitionKey]] = {
            value.name.casefold(): (ordinal, value) for ordinal, value in enumerate(keys)
        }
        self.joins: list[str] = []
        self.parameters: list[object] = []
        self.projections: dict[int, ProjectionRequirement] = {}

    def expression(self, value: Expression) -> str:
        if isinstance(value, Logical):
            operator = "AND" if value.operator is TokenKind.AND else "OR"
            return f"({self.expression(value.left)} {operator} {self.expression(value.right)})"
        if isinstance(value, Negation):
            return f"(NOT {self.expression(value.operand)})"
        if isinstance(value, Comparison):
            column, requirement = self._column(value.field)
            self.parameters.extend(
                (requirement.type_family, self._literal(value.value, requirement.type_name))
            )
            return (
                f"({self._valid(requirement)} AND {column} "
                f"{_comparison_operator(value.operator)} ? )"
            )
        if isinstance(value, Membership):
            column, requirement = self._column(value.field)
            members = " OR ".join(
                self._comparison(column, requirement, TokenKind.EQ, item) for item in value.values
            )
            expression = f"({members})"
            return f"(NOT {expression})" if value.negated else expression
        if isinstance(value, Range):
            column, requirement = self._column(value.field)
            lower = self._comparison(column, requirement, TokenKind.GE, value.lower)
            upper = self._comparison(column, requirement, TokenKind.LE, value.upper)
            expression = f"({lower} AND {upper})"
            return f"(NOT {expression})" if value.negated else expression
        if isinstance(value, Pattern):
            column, requirement = self._column(value.field)
            if requirement.type_family != "string":
                raise UnsupportedPartitionSqlExpression("LIKE requires a string projection")
            self.parameters.extend(
                (requirement.type_family, self._literal(value.value, requirement.type_name))
            )
            expression = f"({self._valid(requirement)} AND mystack_glue_like({column}, ?) = 1)"
            return f"(NOT {expression})" if value.negated else expression
        if isinstance(value, NullCheck):
            column, _ = self._column(value.field)
            expression = f"({column} IS NULL)"
            return f"(NOT {expression})" if value.negated else expression
        raise UnsupportedPartitionSqlExpression(
            f"Unhandled partition expression node: {type(value).__name__}"
        )

    def _comparison(
        self,
        column: str,
        requirement: ProjectionRequirement,
        operator: TokenKind,
        literal: Literal,
    ) -> str:
        self.parameters.extend(
            (requirement.type_family, self._literal(literal, requirement.type_name))
        )
        return f"({self._valid(requirement)} AND {column} {_comparison_operator(operator)} ? )"

    def _column(self, field: str) -> tuple[str, ProjectionRequirement]:
        resolved = self._fields.get(field.casefold())
        if resolved is None:
            raise UnsupportedPartitionSqlExpression("Bound expression referenced an unknown key")
        ordinal, key = resolved
        requirement = self.projections.get(ordinal)
        if requirement is None:
            try:
                family = self._projector.type_family(key.type_name)
            except PartitionValueError as error:
                raise UnsupportedPartitionSqlExpression(str(error)) from error
            requirement = ProjectionRequirement(ordinal, key.type_name, family)
            self.projections[ordinal] = requirement
            alias = _alias(ordinal)
            self.joins.append(
                f"JOIN catalog_partition_value_projections AS {alias} "
                f"ON {alias}.partition_id = p.partition_id AND {alias}.ordinal = {ordinal}"
            )
        return _projection_column(_alias(ordinal), requirement.type_family), requirement

    def _literal(self, literal: Literal, type_name: str) -> str | None:
        try:
            return self._projector.literal(literal.value, type_name)
        except PartitionValueError as error:
            raise UnsupportedPartitionSqlExpression(str(error)) from error

    @staticmethod
    def _valid(requirement: ProjectionRequirement) -> str:
        alias = _alias(requirement.ordinal)
        return f"({alias}.conversion_valid = 1 AND {alias}.type_family = ?)"


def _alias(ordinal: int) -> str:
    return f"pv_{ordinal}"


def _projection_column(alias: str, family: str) -> str:
    columns = {
        "string": "string_value COLLATE BINARY",
        "date": "date_value COLLATE BINARY",
        "timestamp": "timestamp_value COLLATE BINARY",
        "int": "numeric_value COLLATE MYSTACK_NUMERIC",
        "bigint": "numeric_value COLLATE MYSTACK_NUMERIC",
        "long": "numeric_value COLLATE MYSTACK_NUMERIC",
        "tinyint": "numeric_value COLLATE MYSTACK_NUMERIC",
        "smallint": "numeric_value COLLATE MYSTACK_NUMERIC",
        "decimal": "numeric_value COLLATE MYSTACK_NUMERIC",
    }
    try:
        return f"{alias}.{columns[family]}"
    except KeyError as error:
        raise UnsupportedPartitionSqlExpression(
            f"Unsupported partition projection family {family!r}"
        ) from error


def _comparison_operator(operator: TokenKind) -> str:
    operators = {
        TokenKind.EQ: "=",
        TokenKind.NE: "!=",
        TokenKind.GT: ">",
        TokenKind.GE: ">=",
        TokenKind.LT: "<",
        TokenKind.LE: "<=",
    }
    try:
        return operators[operator]
    except KeyError as error:
        raise UnsupportedPartitionSqlExpression(
            f"Unsupported comparison token {operator.name}"
        ) from error
