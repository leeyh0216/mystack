# Generated from GluePartitionExpression.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,22,105,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,1,0,1,0,1,0,1,1,1,1,1,2,1,2,1,2,5,2,29,
        8,2,10,2,12,2,32,9,2,1,3,1,3,1,3,5,3,37,8,3,10,3,12,3,40,9,3,1,4,
        1,4,1,4,3,4,45,8,4,1,5,1,5,1,5,1,5,1,5,3,5,52,8,5,1,6,1,6,1,6,1,
        6,1,6,1,6,1,6,3,6,61,8,6,1,6,1,6,1,6,1,6,3,6,67,8,6,1,6,1,6,1,6,
        1,6,1,6,5,6,74,8,6,10,6,12,6,77,9,6,1,6,1,6,1,6,1,6,3,6,83,8,6,1,
        6,1,6,1,6,1,6,1,6,1,6,1,6,3,6,92,8,6,1,6,1,6,1,6,3,6,97,8,6,1,7,
        1,7,1,8,1,8,1,9,1,9,1,9,0,0,10,0,2,4,6,8,10,12,14,16,18,0,3,1,0,
        1,6,2,0,18,18,21,21,2,0,14,14,19,20,107,0,20,1,0,0,0,2,23,1,0,0,
        0,4,25,1,0,0,0,6,33,1,0,0,0,8,44,1,0,0,0,10,51,1,0,0,0,12,96,1,0,
        0,0,14,98,1,0,0,0,16,100,1,0,0,0,18,102,1,0,0,0,20,21,3,2,1,0,21,
        22,5,0,0,1,22,1,1,0,0,0,23,24,3,4,2,0,24,3,1,0,0,0,25,30,3,6,3,0,
        26,27,5,8,0,0,27,29,3,6,3,0,28,26,1,0,0,0,29,32,1,0,0,0,30,28,1,
        0,0,0,30,31,1,0,0,0,31,5,1,0,0,0,32,30,1,0,0,0,33,38,3,8,4,0,34,
        35,5,7,0,0,35,37,3,8,4,0,36,34,1,0,0,0,37,40,1,0,0,0,38,36,1,0,0,
        0,38,39,1,0,0,0,39,7,1,0,0,0,40,38,1,0,0,0,41,42,5,9,0,0,42,45,3,
        8,4,0,43,45,3,10,5,0,44,41,1,0,0,0,44,43,1,0,0,0,45,9,1,0,0,0,46,
        47,5,15,0,0,47,48,3,2,1,0,48,49,5,16,0,0,49,52,1,0,0,0,50,52,3,12,
        6,0,51,46,1,0,0,0,51,50,1,0,0,0,52,11,1,0,0,0,53,54,3,16,8,0,54,
        55,3,14,7,0,55,56,3,18,9,0,56,97,1,0,0,0,57,58,3,16,8,0,58,60,5,
        13,0,0,59,61,5,9,0,0,60,59,1,0,0,0,60,61,1,0,0,0,61,62,1,0,0,0,62,
        63,5,14,0,0,63,97,1,0,0,0,64,66,3,16,8,0,65,67,5,9,0,0,66,65,1,0,
        0,0,66,67,1,0,0,0,67,68,1,0,0,0,68,69,5,10,0,0,69,70,5,15,0,0,70,
        75,3,18,9,0,71,72,5,17,0,0,72,74,3,18,9,0,73,71,1,0,0,0,74,77,1,
        0,0,0,75,73,1,0,0,0,75,76,1,0,0,0,76,78,1,0,0,0,77,75,1,0,0,0,78,
        79,5,16,0,0,79,97,1,0,0,0,80,82,3,16,8,0,81,83,5,9,0,0,82,81,1,0,
        0,0,82,83,1,0,0,0,83,84,1,0,0,0,84,85,5,11,0,0,85,86,3,18,9,0,86,
        87,5,7,0,0,87,88,3,18,9,0,88,97,1,0,0,0,89,91,3,16,8,0,90,92,5,9,
        0,0,91,90,1,0,0,0,91,92,1,0,0,0,92,93,1,0,0,0,93,94,5,12,0,0,94,
        95,3,18,9,0,95,97,1,0,0,0,96,53,1,0,0,0,96,57,1,0,0,0,96,64,1,0,
        0,0,96,80,1,0,0,0,96,89,1,0,0,0,97,13,1,0,0,0,98,99,7,0,0,0,99,15,
        1,0,0,0,100,101,7,1,0,0,101,17,1,0,0,0,102,103,7,2,0,0,103,19,1,
        0,0,0,10,30,38,44,51,60,66,75,82,91,96
    ]

class GluePartitionExpressionParser ( Parser ):

    grammarFileName = "GluePartitionExpression.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "'>='", "'>'",
                     "'<='", "'<'", "'AND'", "'OR'", "'NOT'", "'IN'", "'BETWEEN'",
                     "'LIKE'", "'IS'", "'NULL'", "'('", "')'", "','" ]

    symbolicNames = [ "<INVALID>", "EQ", "NE", "GE", "GT", "LE", "LT", "AND",
                      "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS", "NULL",
                      "LEFT_PAREN", "RIGHT_PAREN", "COMMA", "QUOTED_IDENTIFIER",
                      "STRING", "NUMBER", "IDENTIFIER", "WS" ]

    RULE_parse = 0
    RULE_expression = 1
    RULE_orExpression = 2
    RULE_andExpression = 3
    RULE_notExpression = 4
    RULE_primaryExpression = 5
    RULE_predicate = 6
    RULE_comparisonOperator = 7
    RULE_identifier = 8
    RULE_literal = 9

    ruleNames =  [ "parse", "expression", "orExpression", "andExpression",
                   "notExpression", "primaryExpression", "predicate", "comparisonOperator",
                   "identifier", "literal" ]

    EOF = Token.EOF
    EQ=1
    NE=2
    GE=3
    GT=4
    LE=5
    LT=6
    AND=7
    OR=8
    NOT=9
    IN=10
    BETWEEN=11
    LIKE=12
    IS=13
    NULL=14
    LEFT_PAREN=15
    RIGHT_PAREN=16
    COMMA=17
    QUOTED_IDENTIFIER=18
    STRING=19
    NUMBER=20
    IDENTIFIER=21
    WS=22

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ParseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.ExpressionContext,0)


        def EOF(self):
            return self.getToken(GluePartitionExpressionParser.EOF, 0)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_parse




    def parse(self):

        localctx = GluePartitionExpressionParser.ParseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_parse)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 20
            self.expression()
            self.state = 21
            self.match(GluePartitionExpressionParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def orExpression(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.OrExpressionContext,0)


        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_expression




    def expression(self):

        localctx = GluePartitionExpressionParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 23
            self.orExpression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class OrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def andExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(GluePartitionExpressionParser.AndExpressionContext)
            else:
                return self.getTypedRuleContext(GluePartitionExpressionParser.AndExpressionContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(GluePartitionExpressionParser.OR)
            else:
                return self.getToken(GluePartitionExpressionParser.OR, i)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_orExpression




    def orExpression(self):

        localctx = GluePartitionExpressionParser.OrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_orExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 25
            self.andExpression()
            self.state = 30
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==8:
                self.state = 26
                self.match(GluePartitionExpressionParser.OR)
                self.state = 27
                self.andExpression()
                self.state = 32
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AndExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def notExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(GluePartitionExpressionParser.NotExpressionContext)
            else:
                return self.getTypedRuleContext(GluePartitionExpressionParser.NotExpressionContext,i)


        def AND(self, i:int=None):
            if i is None:
                return self.getTokens(GluePartitionExpressionParser.AND)
            else:
                return self.getToken(GluePartitionExpressionParser.AND, i)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_andExpression




    def andExpression(self):

        localctx = GluePartitionExpressionParser.AndExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_andExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 33
            self.notExpression()
            self.state = 38
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==7:
                self.state = 34
                self.match(GluePartitionExpressionParser.AND)
                self.state = 35
                self.notExpression()
                self.state = 40
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NotExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NOT(self):
            return self.getToken(GluePartitionExpressionParser.NOT, 0)

        def notExpression(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.NotExpressionContext,0)


        def primaryExpression(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.PrimaryExpressionContext,0)


        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_notExpression




    def notExpression(self):

        localctx = GluePartitionExpressionParser.NotExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_notExpression)
        try:
            self.state = 44
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [9]:
                self.enterOuterAlt(localctx, 1)
                self.state = 41
                self.match(GluePartitionExpressionParser.NOT)
                self.state = 42
                self.notExpression()
                pass
            elif token in [15, 18, 21]:
                self.enterOuterAlt(localctx, 2)
                self.state = 43
                self.primaryExpression()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PrimaryExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LEFT_PAREN(self):
            return self.getToken(GluePartitionExpressionParser.LEFT_PAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.ExpressionContext,0)


        def RIGHT_PAREN(self):
            return self.getToken(GluePartitionExpressionParser.RIGHT_PAREN, 0)

        def predicate(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.PredicateContext,0)


        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_primaryExpression




    def primaryExpression(self):

        localctx = GluePartitionExpressionParser.PrimaryExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_primaryExpression)
        try:
            self.state = 51
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [15]:
                self.enterOuterAlt(localctx, 1)
                self.state = 46
                self.match(GluePartitionExpressionParser.LEFT_PAREN)
                self.state = 47
                self.expression()
                self.state = 48
                self.match(GluePartitionExpressionParser.RIGHT_PAREN)
                pass
            elif token in [18, 21]:
                self.enterOuterAlt(localctx, 2)
                self.state = 50
                self.predicate()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PredicateContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.IdentifierContext,0)


        def comparisonOperator(self):
            return self.getTypedRuleContext(GluePartitionExpressionParser.ComparisonOperatorContext,0)


        def literal(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(GluePartitionExpressionParser.LiteralContext)
            else:
                return self.getTypedRuleContext(GluePartitionExpressionParser.LiteralContext,i)


        def IS(self):
            return self.getToken(GluePartitionExpressionParser.IS, 0)

        def NULL(self):
            return self.getToken(GluePartitionExpressionParser.NULL, 0)

        def NOT(self):
            return self.getToken(GluePartitionExpressionParser.NOT, 0)

        def IN(self):
            return self.getToken(GluePartitionExpressionParser.IN, 0)

        def LEFT_PAREN(self):
            return self.getToken(GluePartitionExpressionParser.LEFT_PAREN, 0)

        def RIGHT_PAREN(self):
            return self.getToken(GluePartitionExpressionParser.RIGHT_PAREN, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(GluePartitionExpressionParser.COMMA)
            else:
                return self.getToken(GluePartitionExpressionParser.COMMA, i)

        def BETWEEN(self):
            return self.getToken(GluePartitionExpressionParser.BETWEEN, 0)

        def AND(self):
            return self.getToken(GluePartitionExpressionParser.AND, 0)

        def LIKE(self):
            return self.getToken(GluePartitionExpressionParser.LIKE, 0)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_predicate




    def predicate(self):

        localctx = GluePartitionExpressionParser.PredicateContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_predicate)
        self._la = 0 # Token type
        try:
            self.state = 96
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 53
                self.identifier()
                self.state = 54
                self.comparisonOperator()
                self.state = 55
                self.literal()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 57
                self.identifier()
                self.state = 58
                self.match(GluePartitionExpressionParser.IS)
                self.state = 60
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==9:
                    self.state = 59
                    self.match(GluePartitionExpressionParser.NOT)


                self.state = 62
                self.match(GluePartitionExpressionParser.NULL)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 64
                self.identifier()
                self.state = 66
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==9:
                    self.state = 65
                    self.match(GluePartitionExpressionParser.NOT)


                self.state = 68
                self.match(GluePartitionExpressionParser.IN)
                self.state = 69
                self.match(GluePartitionExpressionParser.LEFT_PAREN)
                self.state = 70
                self.literal()
                self.state = 75
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==17:
                    self.state = 71
                    self.match(GluePartitionExpressionParser.COMMA)
                    self.state = 72
                    self.literal()
                    self.state = 77
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                self.state = 78
                self.match(GluePartitionExpressionParser.RIGHT_PAREN)
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 80
                self.identifier()
                self.state = 82
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==9:
                    self.state = 81
                    self.match(GluePartitionExpressionParser.NOT)


                self.state = 84
                self.match(GluePartitionExpressionParser.BETWEEN)
                self.state = 85
                self.literal()
                self.state = 86
                self.match(GluePartitionExpressionParser.AND)
                self.state = 87
                self.literal()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 89
                self.identifier()
                self.state = 91
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==9:
                    self.state = 90
                    self.match(GluePartitionExpressionParser.NOT)


                self.state = 93
                self.match(GluePartitionExpressionParser.LIKE)
                self.state = 94
                self.literal()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ComparisonOperatorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EQ(self):
            return self.getToken(GluePartitionExpressionParser.EQ, 0)

        def NE(self):
            return self.getToken(GluePartitionExpressionParser.NE, 0)

        def GT(self):
            return self.getToken(GluePartitionExpressionParser.GT, 0)

        def GE(self):
            return self.getToken(GluePartitionExpressionParser.GE, 0)

        def LT(self):
            return self.getToken(GluePartitionExpressionParser.LT, 0)

        def LE(self):
            return self.getToken(GluePartitionExpressionParser.LE, 0)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_comparisonOperator




    def comparisonOperator(self):

        localctx = GluePartitionExpressionParser.ComparisonOperatorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_comparisonOperator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 98
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 126) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class IdentifierContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(GluePartitionExpressionParser.IDENTIFIER, 0)

        def QUOTED_IDENTIFIER(self):
            return self.getToken(GluePartitionExpressionParser.QUOTED_IDENTIFIER, 0)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_identifier




    def identifier(self):

        localctx = GluePartitionExpressionParser.IdentifierContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_identifier)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 100
            _la = self._input.LA(1)
            if not(_la==18 or _la==21):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(GluePartitionExpressionParser.STRING, 0)

        def NUMBER(self):
            return self.getToken(GluePartitionExpressionParser.NUMBER, 0)

        def NULL(self):
            return self.getToken(GluePartitionExpressionParser.NULL, 0)

        def getRuleIndex(self):
            return GluePartitionExpressionParser.RULE_literal




    def literal(self):

        localctx = GluePartitionExpressionParser.LiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_literal)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 102
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1589248) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx
