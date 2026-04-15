"""
pytest tests for the S-V-O logic language project.

To run these tests:
    pytest -q

These tests exercise parsing, simple facts, rules (symmetric love), grandparent rule,
and a no-solution case.
"""

import pytest

from svo.parser import parse_kb, parse_query
from svo.interpreter import KB, solve, term_to_readable
from svo.ast import clause_to_str


def test_parse_fact():
    clauses = parse_kb('john likes mary.')
    assert len(clauses) == 1
    cl = clauses[0]
    assert cl.is_fact()
    assert clause_to_str(cl) == 'john likes mary.'


def test_query_simple_fact():
    kb = KB(parse_kb('john likes mary.'))
    q = parse_query('X likes mary.')
    sols = list(solve(kb, [q]))
    assert len(sols) == 1
    subst, trace = sols[0]
    assert 'X' in subst
    assert term_to_readable(subst['X']) == 'john'


def test_rule_symmetric_love():
    kb_text = (
        'john likes mary. '
        'mary likes john. '
        'X loves Y if X likes Y, Y likes X.'
    )
    kb = KB(parse_kb(kb_text))
    q = parse_query('X loves mary.')
    sols = list(solve(kb, [q]))
    # expecting at least one solution where X = john
    assert any(term_to_readable(sol[0]['X']) == 'john' for sol in sols)


def test_grandparent_rule():
    kb_text = (
        'alice parent_of carol. '
        'carol parent_of dave. '
        'X grandparent_of Z if X parent_of Y, Y parent_of Z.'
    )
    kb = KB(parse_kb(kb_text))
    q = parse_query('X grandparent_of dave.')
    sols = list(solve(kb, [q]))
    assert len(sols) == 1
    subst, _ = sols[0]
    assert term_to_readable(subst['X']) == 'alice'


def test_no_solution_returns_empty():
    kb = KB(parse_kb('john likes mary.'))
    q = parse_query('X loves mary.')
    sols = list(solve(kb, [q]))
    assert len(sols) == 0
