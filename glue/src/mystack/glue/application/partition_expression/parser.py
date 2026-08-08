"""ANTLR4 parse-tree to application AST adapter for Glue expressions.

AWS documents a SQL-WHERE-like expression parsed by JSQLParser. Mystack owns a
smaller ANTLR4 grammar for the documented public subset:
https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

from __future__ import annotations

from typing import NoReturn

from antlr4 import CommonTokenStream, InputStream, Token
from antlr4.error.ErrorListener import ErrorListener
from mystack.glue.application.partition_expression.generated.GluePartitionExpressionLexer import (
    GluePartitionExpressionLexer,
)
from mystack.glue.application.partition_expression.generated.GluePartitionExpressionParser import (
    GluePartitionExpressionParser as GeneratedParser,
)
from mystack.glue.application.partition_expression.model import (
    Comparison,
    Expression,
    Literal,
    Logical,
    Membership,
    Negation,
    NullCheck,
    PartitionExpressionPolicy,
    Pattern,
    Range,
    TokenKind,
)
from mystack.glue.domain import InvalidInputError

_OPERATORS = {
    "=": TokenKind.EQ,
    "==": TokenKind.EQ,
    "<>": TokenKind.NE,
    "!=": TokenKind.NE,
    ">": TokenKind.GT,
    ">=": TokenKind.GE,
    "<": TokenKind.LT,
    "<=": TokenKind.LE,
}


class RaisingSyntaxErrorListener(ErrorListener):
    """Translate ANTLR recovery callbacks into the modeled Glue input error."""

    def syntaxError(
        self,
        recognizer: object,
        offending_symbol: object,
        line: int,
        column: int,
        message: str,
        exception: object,
    ) -> NoReturn:
        del recognizer, offending_symbol, message, exception
        raise InvalidInputError(f"Invalid partition expression at line {line}, column {column}")


class PartitionExpressionParser:
    """Apply resource bounds, invoke generated code, then build an immutable AST."""

    def __init__(self, policy: PartitionExpressionPolicy) -> None:
        self._policy = policy

    def parse(self, source: str) -> Expression:
        if len(source) > self._policy.max_length:
            raise InvalidInputError(
                f"Partition expression exceeds {self._policy.max_length} characters"
            )
        error_listener = RaisingSyntaxErrorListener()
        lexer = GluePartitionExpressionLexer(InputStream(source))
        lexer.removeErrorListeners()
        lexer.addErrorListener(error_listener)
        tokens = CommonTokenStream(lexer)
        tokens.fill()
        token_count = sum(token.type != Token.EOF for token in tokens.tokens)
        if token_count > self._policy.max_tokens:
            raise InvalidInputError(
                f"Partition expression exceeds {self._policy.max_tokens} tokens"
            )
        parser = GeneratedParser(tokens)
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)
        tree = parser.parse()
        return self._or_expression(tree.expression().orExpression())

    def _or_expression(self, context: GeneratedParser.OrExpressionContext) -> Expression:
        operands = context.andExpression()
        expression = self._and_expression(operands[0])
        for operand in operands[1:]:
            expression = Logical(TokenKind.OR, expression, self._and_expression(operand))
        return expression

    def _and_expression(self, context: GeneratedParser.AndExpressionContext) -> Expression:
        operands = context.notExpression()
        expression = self._not_expression(operands[0])
        for operand in operands[1:]:
            expression = Logical(TokenKind.AND, expression, self._not_expression(operand))
        return expression

    def _not_expression(self, context: GeneratedParser.NotExpressionContext) -> Expression:
        nested = context.notExpression()
        if nested is not None:
            return Negation(self._not_expression(nested))
        return self._primary_expression(context.primaryExpression())

    def _primary_expression(
        self,
        context: GeneratedParser.PrimaryExpressionContext,
    ) -> Expression:
        nested = context.expression()
        if nested is not None:
            return self._or_expression(nested.orExpression())
        return self._predicate(context.predicate())

    def _predicate(self, context: GeneratedParser.PredicateContext) -> Expression:
        field = self._identifier(context.identifier())
        literals = tuple(self._literal(value) for value in context.literal())
        comparison = context.comparisonOperator()
        if comparison is not None:
            return Comparison(field, _OPERATORS[comparison.getText()], literals[0])
        negated = context.NOT() is not None
        if context.IS() is not None:
            return NullCheck(field, negated)
        if context.IN() is not None:
            return Membership(field, literals, negated)
        if context.BETWEEN() is not None:
            return Range(field, literals[0], literals[1], negated)
        if context.LIKE() is not None:
            return Pattern(field, literals[0], negated)
        raise TypeError("ANTLR produced an unknown partition predicate")

    @staticmethod
    def _identifier(context: GeneratedParser.IdentifierContext) -> str:
        text = context.getText()
        return PartitionExpressionParser._unquote(text) if text.startswith("`") else text

    @staticmethod
    def _literal(context: GeneratedParser.LiteralContext) -> Literal:
        if context.NULL() is not None:
            return Literal(None)
        text = context.getText()
        if context.STRING() is not None:
            text = PartitionExpressionParser._unquote(text)
        return Literal(text)

    @staticmethod
    def _unquote(text: str) -> str:
        delimiter = text[0]
        inner = text[1:-1]
        value: list[str] = []
        position = 0
        while position < len(inner):
            character = inner[position]
            if character == delimiter and position + 1 < len(inner):
                if inner[position + 1] == delimiter:
                    value.append(delimiter)
                    position += 2
                    continue
            if character == "\\" and position + 1 < len(inner):
                value.append(inner[position + 1])
                position += 2
                continue
            value.append(character)
            position += 1
        return "".join(value)
