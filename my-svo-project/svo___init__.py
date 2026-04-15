"""
svo package initializer — exports convenient functions and classes.
"""
from .parser import parse_kb, parse_query, Parser
from .interpreter import KB, solve, ProofStep
from .ast import Atom, Variable, Literal, Clause
from .lexer import simple_tokenize

__all__ = [
    'parse_kb', 'parse_query', 'Parser',
    'KB', 'solve', 'ProofStep',
    'Atom', 'Variable', 'Literal', 'Clause',
    'simple_tokenize'
]
