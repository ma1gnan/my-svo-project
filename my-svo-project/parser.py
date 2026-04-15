"""
Parser module for the S-V-O logic language project.

Provides:
- Parser: recursive-descent parser that consumes tokens (from lexer.simple_tokenize) and
  produces AST objects (from ast.py): Clause, Literal, Atom, Variable
- parse_kb(text) -> List[Clause]
- parse_query(text) -> Literal

This module intentionally does not construct KB objects (interpreter.py is responsible for that)
to avoid circular imports.
"""
from typing import List, Optional

from .ast import Atom, Variable, Literal, Clause
from .lexer import Token, simple_tokenize


class ParserError(Exception):
    """Raised when a parse error occurs."""


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- token helpers ---
    def peek(self) -> Optional[Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> Token:
        t = self.peek()
        if t is None:
            raise ParserError('Unexpected end of input')
        self.pos += 1
        return t

    def accept(self, *types: str) -> Optional[Token]:
        t = self.peek()
        if t and t.type in types:
            self.pos += 1
            return t
        return None

    def expect(self, *types: str) -> Token:
        t = self.next()
        if t.type not in types:
            raise ParserError(f"Expected token types {types}, got {t.type} ('{t.value}') at pos {t.pos}")
        return t

    # --- grammar parsing ---
    def parse_program(self) -> List[Clause]:
        clauses: List[Clause] = []
        while self.peek() is not None:
            # skip stray dots
            if self.peek().type == 'DOT':
                self.next()
                continue
            clause = self.parse_clause()
            # each clause must end with a DOT
            self.expect('DOT')
            clauses.append(clause)
        return clauses

    def parse_clause(self) -> Clause:
        head = self.parse_literal()
        if self.accept('IF'):
            body = self.parse_body()
            return Clause(head, body)
        return Clause(head, [])

    def parse_body(self) -> List[Literal]:
        lits: List[Literal] = []
        lits.append(self.parse_literal())
        while self.accept('COMMA'):
            lits.append(self.parse_literal())
        return lits

    def parse_literal(self) -> Literal:
        # literal := subject verb object
        subj_tok = self.expect('IDENT', 'QUOTED')
        subj = self.token_to_term(subj_tok)
        verb_tok = self.expect('IDENT', 'QUOTED')
        verb = Atom(verb_tok.value)
        obj_tok = self.expect('IDENT', 'QUOTED', 'NUMBER')
        obj = self.token_to_term(obj_tok)
        return Literal(subj, verb, obj)

    def token_to_term(self, tok: Token):
        if tok.type == 'IDENT':
            # variables start with uppercase or are '_' (anonymous)
            if tok.value == '_' or tok.value[0].isupper():
                return Variable(tok.value)
            return Atom(tok.value)
        if tok.type == 'QUOTED':
            return Atom(tok.value)
        if tok.type == 'NUMBER':
            # treat numbers as atoms for simplicity
            return Atom(tok.value)
        raise ParserError(f"Cannot convert token {tok}")


# --- convenience functions ---
def parse_kb(text: str) -> List[Clause]:
    """Parse a knowledge-base text into a list of Clause objects.

    Does not construct a KB interpreter object; that is handled by interpreter.KB.
    """
    tokens = simple_tokenize(text)
    parser = Parser(tokens)
    return parser.parse_program()


def parse_query(text: str) -> Literal:
    """Parse a single query literal from text and return a Literal.

    The text may omit the leading '?-' and should include a terminating period ('.')
    or the caller may add it; the parser expects a literal followed by a DOT in typical use,
    but this helper will parse a standalone literal without enforcing trailing DOT.
    """
    tokens = simple_tokenize(text)
    parser = Parser(tokens)
    # parse one literal (do not require trailing DOT here)
    lit = parser.parse_literal()
    return lit
