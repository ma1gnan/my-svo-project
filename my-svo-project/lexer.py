"""
Lexer / tokenizer for the S-V-O logic language.

Exports:
- Token class (type, value, pos)
- simple_tokenize(text) -> List[Token]

Token types produced: IDENT, QUOTED, NUMBER, DOT, COMMA, IF, QUERY

This tokenizer is intentionally simple and deterministic for the teaching/demo
environment. It favors readability and clear error messages over maximal
robustness.
"""
from typing import List
import re

class Token:
    def __init__(self, type_: str, value: str, pos: int):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.type!r}, {self.value!r}, {self.pos})"


# Simple tokenizer used by the parser. Recognizes identifiers, quoted strings,
# numbers (as atoms), punctuation (., ,), the keyword 'if', and the query prefix '?-'.
def simple_tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # whitespace
        if ch.isspace():
            i += 1
            continue
        # query prefix ?-
        if text.startswith('?-', i):
            tokens.append(Token('QUERY', '?-', i))
            i += 2
            continue
        # keyword: if (must be standalone or followed by non-alnum)
        if text.startswith('if', i) and (i+2 == n or not text[i+2].isalnum()):
            tokens.append(Token('IF', 'if', i))
            i += 2
            continue
        # punctuation
        if ch == '.':
            tokens.append(Token('DOT', '.', i)); i += 1; continue
        if ch == ',':
            tokens.append(Token('COMMA', ',', i)); i += 1; continue
        # quoted string
        if ch == '"':
            start = i
            i += 1
            buf = []
            while i < n:
                if text[i] == '"':
                    break
                if text[i] == '\\' and i + 1 < n:
                    # simple escape handling: include escaped char
                    i += 1
                    buf.append(text[i])
                else:
                    buf.append(text[i])
                i += 1
            else:
                raise SyntaxError(f"Unterminated quoted string starting at {start}")
            tokens.append(Token('QUOTED', ''.join(buf), start))
            i += 1  # consume closing quote
            continue
        # identifier (letters or underscore followed by letters/digits/_)
        if re.match(r'[A-Za-z_]', ch):
            start = i
            i += 1
            while i < n and re.match(r'[A-Za-z0-9_]', text[i]):
                i += 1
            ident = text[start:i]
            tokens.append(Token('IDENT', ident, start))
            continue
        # number (treat as atom)
        if ch.isdigit():
            start = i
            while i < n and text[i].isdigit():
                i += 1
            tokens.append(Token('NUMBER', text[start:i], start))
            continue
        # unknown character
        raise SyntaxError(f"Unexpected character {ch!r} at position {i}")
    return tokens


__all__ = ['Token', 'simple_tokenize']
