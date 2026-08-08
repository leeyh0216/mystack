// AWS Glue GetPartitions Expression grammar implemented with ANTLR4.
// Protocol source: https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
// ANTLR source: https://github.com/antlr/antlr4/blob/4.13.2/doc/getting-started.md
grammar GluePartitionExpression;

options {
    caseInsensitive = true;
}

parse
    : expression EOF
    ;

expression
    : orExpression
    ;

orExpression
    : andExpression (OR andExpression)*
    ;

andExpression
    : notExpression (AND notExpression)*
    ;

notExpression
    : NOT notExpression
    | primaryExpression
    ;

primaryExpression
    : LEFT_PAREN expression RIGHT_PAREN
    | predicate
    ;

predicate
    : identifier comparisonOperator literal
    | identifier IS NOT? NULL
    | identifier NOT? IN LEFT_PAREN literal (COMMA literal)* RIGHT_PAREN
    | identifier NOT? BETWEEN literal AND literal
    | identifier NOT? LIKE literal
    ;

comparisonOperator
    : EQ
    | NE
    | GT
    | GE
    | LT
    | LE
    ;

identifier
    : IDENTIFIER
    | QUOTED_IDENTIFIER
    ;

literal
    : STRING
    | NUMBER
    | NULL
    ;

EQ: '=' | '==';
NE: '<>' | '!=';
GE: '>=';
GT: '>';
LE: '<=';
LT: '<';
AND: 'AND';
OR: 'OR';
NOT: 'NOT';
IN: 'IN';
BETWEEN: 'BETWEEN';
LIKE: 'LIKE';
IS: 'IS';
NULL: 'NULL';
LEFT_PAREN: '(';
RIGHT_PAREN: ')';
COMMA: ',';

QUOTED_IDENTIFIER
    : '`' ('``' | '\\' . | ~[`\\])* '`'
    ;

STRING
    : '\'' ('\'\'' | '\\' . | ~['\\])* '\''
    | '"' ('""' | '\\' . | ~["\\])* '"'
    ;

NUMBER
    : [+-]? (DIGIT+ ('.' DIGIT*)? | '.' DIGIT+)
    ;

IDENTIFIER
    : [a-z_] [a-z0-9_$]*
    ;

fragment DIGIT: [0-9];

WS: [ \t\r\n]+ -> skip;
