"""
interpreter.py

Backward-chaining interpreter and supporting utilities for the S-V-O logic language.

Exports:
- KB(clauses: List[Clause])
- solve(kb: KB, goals: List[Literal], subst: Optional[Subst]) -> Iterator[Tuple[Subst, List[ProofStep]]]
- ProofStep

Dependencies: imports AST classes from .ast (Atom, Variable, Literal, Clause)
"""
from typing import List, Dict, Optional, Iterator, Tuple
from copy import deepcopy

from .ast import Atom, Variable, Literal, Clause

# Type alias for substitutions: variable name -> Term
Subst = Dict[str, object]


class ParserError(Exception):
    pass


class ProofStep:
    def __init__(self, goal: Literal, clause: Clause, subst: Subst):
        self.goal = goal
        self.clause = clause
        self.subst = subst
    def __repr__(self):
        return f"ProofStep(goal={self.goal!r}, clause={self.clause!r}, subst={self.subst!r})"


class KB:
    def __init__(self, clauses: List[Clause]):
        self.clauses: List[Clause] = clauses
        self.index = self.build_index(clauses)

    def build_index(self, clauses: List[Clause]):
        idx = {}
        for c in clauses:
            verb = c.head.verb.name
            idx.setdefault(verb, []).append(c)
        return idx

    def clauses_for_verb(self, verb: str) -> List[Clause]:
        return list(self.index.get(verb, []))


# -----------------------------
# Unification / substitution
# -----------------------------

def is_variable(t) -> bool:
    return isinstance(t, Variable)


def apply_subst_term(t, subst: Subst):
    if is_variable(t):
        name = t.name
        if name in subst:
            return apply_subst_term(subst[name], subst)
        return t
    return t


def occurs_check(var: Variable, term, subst: Subst) -> bool:
    # prevents var = f(... var ...)
    if is_variable(term):
        if term.name == var.name:
            return True
        if term.name in subst:
            return occurs_check(var, subst[term.name], subst)
        return False
    return False


def unify_terms(a, b, subst: Subst) -> Optional[Subst]:
    a = apply_subst_term(a, subst)
    b = apply_subst_term(b, subst)
    if is_variable(a):
        if is_variable(b) and a.name == b.name:
            return subst
        if occurs_check(a, b, subst):
            return None
        new = dict(subst)
        new[a.name] = b
        return new
    if is_variable(b):
        return unify_terms(b, a, subst)
    # both atoms
    if isinstance(a, Atom) and isinstance(b, Atom) and a.name == b.name:
        return subst
    return None


def unify_literals(l1: Literal, l2: Literal, subst: Subst) -> Optional[Subst]:
    # verb names must match
    if l1.verb.name != l2.verb.name:
        return None
    s1 = unify_terms(l1.subject, l2.subject, subst)
    if s1 is None:
        return None
    s2 = unify_terms(l1.object, l2.object, s1)
    return s2


def apply_subst_literal(l: Literal, subst: Subst) -> Literal:
    s = apply_subst_term(l.subject, subst)
    o = apply_subst_term(l.object, subst)
    return Literal(s, l.verb, o)


# -----------------------------
# Standardize-apart (fresh variable names)
# -----------------------------
_var_id_counter = 0


def fresh_var_name(base: str = 'V') -> str:
    global _var_id_counter
    _var_id_counter += 1
    return f"{base}_{_var_id_counter}"


def standardize_apart(clause: Clause) -> Clause:
    var_map: Dict[str, Variable] = {}
    def fresh_term(t):
        if isinstance(t, Variable):
            if t.name not in var_map:
                var_map[t.name] = Variable(fresh_var_name(t.name))
            return var_map[t.name]
        return t
    head = Literal(fresh_term(clause.head.subject), clause.head.verb, fresh_term(clause.head.object))
    body = [Literal(fresh_term(b.subject), b.verb, fresh_term(b.object)) for b in clause.body]
    return Clause(head, body)


# -----------------------------
# Solver (backward chaining, depth-first, SLD)
# -----------------------------

def solve(kb: KB, goals: List[Literal], subst: Optional[Subst] = None) -> Iterator[Tuple[Subst, List[ProofStep]]]:
    if subst is None:
        subst = {}
    if not goals:
        yield subst, []
        return
    first, *rest = goals
    goal = apply_subst_literal(first, subst)
    candidates = kb.clauses_for_verb(goal.verb.name)
    for clause in candidates:
        renamed = standardize_apart(clause)
        u = unify_literals(goal, renamed.head, dict(subst))
        if u is None:
            continue
        new_body = [apply_subst_literal(b, u) for b in renamed.body]
        new_rest = [apply_subst_literal(r, u) for r in rest]
        new_goals = new_body + new_rest
        for sol_subst, trace in solve(kb, new_goals, u):
            step = ProofStep(goal, renamed, u)
            yield sol_subst, [step] + trace


# -----------------------------
# Small helpers for debugging/REPL integration
# -----------------------------

def collect_variables(l: Literal) -> List[Variable]:
    vars: List[Variable] = []
    if isinstance(l.subject, Variable):
        vars.append(l.subject)
    if isinstance(l.object, Variable):
        vars.append(l.object)
    return vars


def term_to_readable(t) -> str:
    if isinstance(t, Atom):
        return t.name
    if isinstance(t, Variable):
        return t.name
    return str(t)
