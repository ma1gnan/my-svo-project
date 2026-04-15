"""
AST definitions for the S-V-O logic language.

Provides:
- Atom, Variable, Literal, Clause classes
- Utilities: literal_to_str, clause_to_str

These definitions match what parser.py and interpreter.py expect.
"""
from typing import List


class Term:
    pass


class Atom(Term):
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"Atom({self.name!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Atom) and self.name == other.name

    def __hash__(self):
        return hash(("Atom", self.name))


class Variable(Term):
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"Var({self.name})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Variable) and self.name == other.name

    def __hash__(self):
        return hash(("Var", self.name))


class Literal:
    def __init__(self, subject: Term, verb: Atom, object_: Term):
        self.subject = subject
        self.verb = verb
        self.object = object_  # `object` is a reserved name in some linters

    def __repr__(self) -> str:
        return f"Literal({self.subject!r}, {self.verb!r}, {self.object!r})"

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Literal) and
            self.subject == other.subject and
            self.verb == other.verb and
            self.object == other.object
        )


class Clause:
    def __init__(self, head: Literal, body: List[Literal] = None):
        self.head = head
        self.body = body or []

    def is_fact(self) -> bool:
        return len(self.body) == 0

    def __repr__(self) -> str:
        return f"Clause(head={self.head!r}, body={self.body!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Clause) and self.head == other.head and self.body == other.body


# ----- pretty-printing helpers -----

def _term_to_str(t: Term) -> str:
    if isinstance(t, Atom):
        # quote atoms with whitespace
        if ' ' in t.name or t.name == '':
            return f'"{t.name}"'
        return t.name
    if isinstance(t, Variable):
        return t.name
    return str(t)


def literal_to_str(lit: Literal) -> str:
    return f"{_term_to_str(lit.subject)} {lit.verb.name} {_term_to_str(lit.object)}"


def clause_to_str(cl: Clause) -> str:
    head = literal_to_str(cl.head)
    if cl.is_fact():
        return head + '.'
    body = ', '.join(literal_to_str(b) for b in cl.body)
    return f"{head} if {body}."
