"""
SVO Logic Language Prototype

Single-file Python 3 script implementing:
- Tokenizer / Lexer
- Recursive-descent parser (facts & rules, S-V-O literals)
- AST classes and pretty printing
- Backward-chaining interpreter (unification, substitution, solve generator)
- Proof-trace capture
- Small REPL to load KB and run queries
- Basic unit tests (unittest)

Usage:
    python SVO_logic_prototype.py         # runs REPL with sample KB
    python SVO_logic_prototype.py --test  # runs unit tests

Language rules (surface): each literal is Subject Verb Object. Variables start with uppercase. Atoms are lowercase or quoted strings. Rules use keyword 'if' and comma-separated bodies. Every clause ends with a period.
"""

import re
import sys
import pprint
from typing import List, Tuple, Dict, Optional, Iterator, Union
import unittest

# -----------------------------
# Lexer / Tokenizer
# -----------------------------

TOKEN_SPEC = [
    ('NUMBER',      r'\d+'),
    ('QUERY',       r'\?\-'),
    ('IF',          r'if\b'),
    ('DOT',         r'\.'),
    ('COMMA',       r','),
    ('QUOTE',       r'"'),
    ('IDENT',       r'[A-Za-z_][A-Za-z0-9_]*'),
    ('SKIP',        r'[ \t\r\n]+'),
    ('MISMATCH',    r'.'),
]

TOK_REGEX = '|'.join('(?P<%s>%s)' % pair for pair in TOKEN_SPEC)

class Token:
    def __init__(self, type_, value, pos):
        self.type = type_
        self.value = value
        self.pos = pos
    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, {self.pos})"


def tokenize(text: str) -> Iterator[Token]:
    pos = 0
    scanner = re.finditer(TOK_REGEX, text)
    for m in scanner:
        kind = m.lastgroup
        value = m.group()
        if kind == 'SKIP':
            pos = m.end()
            continue
        elif kind == 'MISMATCH':
            raise SyntaxError(f"Unexpected character {value!r} at position {m.start()}")
        elif kind == 'QUOTE':
            # parse quoted string
            # find next unescaped quote
            start = m.end()
            end_idx = start
            escaped = False
            buf = []
            while end_idx < len(text):
                ch = text[end_idx]
                if ch == '"' and not escaped:
                    break
                if ch == '\\' and not escaped:
                    escaped = True
                else:
                    buf.append(ch)
                    escaped = False
                end_idx += 1
            else:
                raise SyntaxError(f"Unterminated quoted string starting at {m.start()}")
            value = ''.join(buf)
            pos = end_idx + 1
            yield Token('QUOTED', value, m.start())
            # advance scanner to after closing quote by moving the regex iterator; naive approach is to slice remainder
            scanner = re.finditer(TOK_REGEX, text[pos:])
            for m2 in scanner:
                kind = m2.lastgroup
                value = m2.group()
                break
            # but the outer loop will continue; to avoid complexity, just return to caller; simpler approach: re-tokenize remainder
            # Instead, we'll yield tokens by manual loop; to keep simple, we'll break and restart tokenizer
            rest = text[pos:]
            for tok in tokenize(rest):
                yield Token(tok.type, tok.value, tok.pos + pos)
            return
        else:
            yield Token(kind, value, m.start())
            pos = m.end()

# Simpler tokenizer for predictable S-V-O language (handles quoted strings and identifiers)

def simple_tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith('?-', i):
            tokens.append(Token('QUERY', '?-', i)); i += 2; continue
        if text.startswith('if', i) and (i+2==n or not text[i+2].isalnum()):
            tokens.append(Token('IF','if',i)); i += 2; continue
        if ch == '.': tokens.append(Token('DOT','.',i)); i+=1; continue
        if ch == ',': tokens.append(Token('COMMA',',',i)); i+=1; continue
        if ch == '"':
            # quoted string
            i += 1
            start = i
            buf = []
            while i < n:
                if text[i] == '"':
                    break
                if text[i] == '\\' and i+1 < n:
                    i += 1
                    buf.append(text[i])
                else:
                    buf.append(text[i])
                i += 1
            else:
                raise SyntaxError(f"Unterminated quoted string at pos {start}")
            tokens.append(Token('QUOTED', ''.join(buf), start-1))
            i += 1
            continue
        # identifier (variable or atom)
        if re.match(r'[A-Za-z_]', ch):
            start = i
            i += 1
            while i < n and re.match(r'[A-Za-z0-9_]', text[i]):
                i += 1
            ident = text[start:i]
            tokens.append(Token('IDENT', ident, start))
            continue
        # numbers (treat as atoms)
        if ch.isdigit():
            start = i
            while i < n and text[i].isdigit(): i += 1
            tokens.append(Token('NUMBER', text[start:i], start))
            continue
        raise SyntaxError(f"Unexpected character {ch!r} at pos {i}")
    return tokens

# -----------------------------
# AST classes
# -----------------------------

class Term:
    pass

class Atom(Term):
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return f'Atom({self.name!r})'
    def __eq__(self, other):
        return isinstance(other, Atom) and self.name == other.name

class Variable(Term):
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return f'Var({self.name})'
    def __eq__(self, other):
        return isinstance(other, Variable) and self.name == other.name

class Literal:
    def __init__(self, subject: Term, verb: Atom, object_: Term):
        self.subject = subject
        self.verb = verb
        self.object = object_
    def __repr__(self):
        return f'Literal({self.subject!r}, {self.verb!r}, {self.object!r})'

class Clause:
    def __init__(self, head: Literal, body: Optional[List[Literal]] = None):
        self.head = head
        self.body = body or []
    def is_fact(self) -> bool:
        return len(self.body) == 0
    def __repr__(self):
        return f'Clause(head={self.head!r}, body={self.body!r})'

# -----------------------------
# Parser (recursive-descent)
# -----------------------------

class ParserError(Exception): pass

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    def next(self) -> Token:
        t = self.peek()
        if t is None:
            raise ParserError('Unexpected end of input')
        self.pos += 1
        return t
    def accept(self, *types) -> Optional[Token]:
        t = self.peek()
        if t and t.type in types:
            self.pos += 1
            return t
        return None
    def expect(self, *types) -> Token:
        t = self.next()
        if t.type not in types:
            raise ParserError(f"Expected token types {types}, got {t.type} ({t.value}) at pos {t.pos}")
        return t

    def parse_program(self) -> List[Clause]:
        clauses: List[Clause] = []
        while self.peek() is not None:
            # handle optional final trailing tokens
            if self.peek().type == 'DOT':
                self.next(); continue
            clause = self.parse_clause()
            # expect dot
            tok = self.expect('DOT')
            clauses.append(clause)
        return clauses

    def parse_clause(self) -> Clause:
        head = self.parse_literal()
        if self.accept('IF'):
            body = self.parse_body()
            return Clause(head, body)
        else:
            return Clause(head, [])

    def parse_body(self) -> List[Literal]:
        lits = []
        lits.append(self.parse_literal())
        while self.accept('COMMA'):
            lits.append(self.parse_literal())
        return lits

    def parse_literal(self) -> Literal:
        # expect subject verb object
        subj_tok = self.expect('IDENT','QUOTED')
        subj = self.token_to_term(subj_tok)
        verb_tok = self.expect('IDENT','QUOTED')
        verb = Atom(verb_tok.value)
        obj_tok = self.expect('IDENT','QUOTED','NUMBER')
        obj = self.token_to_term(obj_tok)
        return Literal(subj, verb, obj)

    def token_to_term(self, tok: Token) -> Term:
        if tok.type == 'IDENT':
            if tok.value[0].isupper() or tok.value == '_':
                return Variable(tok.value)
            else:
                return Atom(tok.value)
        elif tok.type == 'QUOTED':
            return Atom(tok.value)
        elif tok.type == 'NUMBER':
            return Atom(tok.value)
        else:
            raise ParserError(f"Cannot convert token {tok}")

# -----------------------------
# Utility: pretty printing AST
# -----------------------------

def literal_to_str(lit: Literal) -> str:
    def term_str(t: Term) -> str:
        if isinstance(t, Atom):
            # quote atoms with spaces
            if ' ' in t.name or t.name == '':
                return f'"{t.name}"'
            return t.name
        elif isinstance(t, Variable):
            return t.name
        else:
            return str(t)
    return f"{term_str(lit.subject)} {lit.verb.name} {term_str(lit.object)}"

def clause_to_str(cl: Clause) -> str:
    head = literal_to_str(cl.head)
    if cl.is_fact():
        return head + '.'
    else:
        body = ', '.join(literal_to_str(b) for b in cl.body)
        return f"{head} if {body}."

# -----------------------------
# Unification & Substitution
# -----------------------------

Subst = Dict[str, Term]  # map variable name -> Term


def is_variable(t: Term) -> bool:
    return isinstance(t, Variable)


def occurs_check(var: Variable, term: Term, subst: Subst) -> bool:
    # simple occurs-check to avoid infinite terms
    if is_variable(term):
        if term.name == var.name:
            return True
        if term.name in subst:
            return occurs_check(var, subst[term.name], subst)
        return False
    # atoms cannot contain variable references
    return False


def apply_subst_term(t: Term, subst: Subst) -> Term:
    if is_variable(t):
        if t.name in subst:
            return apply_subst_term(subst[t.name], subst)
        return t
    return t


def unify_terms(a: Term, b: Term, subst: Subst) -> Optional[Subst]:
    a = apply_subst_term(a, subst)
    b = apply_subst_term(b, subst)
    if is_variable(a):
        if isinstance(b, Variable) and a.name == b.name:
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
    # verbs must match exactly
    if l1.verb.name != l2.verb.name:
        return None
    s1 = unify_terms(l1.subject, l2.subject, subst)
    if s1 is None: return None
    s2 = unify_terms(l1.object, l2.object, s1)
    return s2


def apply_subst_literal(l: Literal, subst: Subst) -> Literal:
    s = apply_subst_term(l.subject, subst)
    o = apply_subst_term(l.object, subst)
    return Literal(s, l.verb, o)

# -----------------------------
# Interpreter (backward chaining)
# -----------------------------

class ProofStep:
    def __init__(self, goal: Literal, clause: Clause, subst: Subst):
        self.goal = goal
        self.clause = clause
        self.subst = subst
    def __repr__(self):
        return f'ProofStep(goal={self.goal!r}, clause={self.clause!r}, subst={self.subst!r})'

class KB:
    def __init__(self, clauses: List[Clause]):
        self.clauses = clauses
        self.index = self.build_index(clauses)
    def build_index(self, clauses: List[Clause]):
        idx = {}
        for c in clauses:
            verb = c.head.verb.name
            idx.setdefault(verb, []).append(c)
        return idx
    def clauses_for_verb(self, verb: str) -> List[Clause]:
        return list(self.index.get(verb, []))


def solve(kb: KB, goals: List[Literal], subst: Optional[Subst] = None) -> Iterator[Tuple[Subst, List[ProofStep]]]:
    if subst is None: subst = {}
    if not goals:
        yield subst, []
        return
    # take first goal
    first, *rest = goals
    # apply current substitution to the goal
    goal = apply_subst_literal(first, subst)
    # find candidate clauses by verb
    candidates = kb.clauses_for_verb(goal.verb.name)
    for clause in candidates:
        # rename clause variables (standardize apart) to avoid name clashes
        renamed_clause = standardize_apart(clause)
        # try unify goal with clause head
        u = unify_literals(goal, renamed_clause.head, dict(subst))
        if u is None:
            continue
        # produce new goals: clause body (with u applied) followed by rest (with u applied later)
        new_body = [apply_subst_literal(b, u) for b in renamed_clause.body]
        new_rest = [apply_subst_literal(r, u) for r in rest]
        new_goals = new_body + new_rest
        # for each solution for new_goals, yield composed substitution and proof trace
        for sol_subst, trace in solve(kb, new_goals, u):
            step = ProofStep(goal, renamed_clause, u)
            yield sol_subst, [step] + trace

_var_id_counter = 0

def fresh_var_name(base: str = 'V') -> str:
    global _var_id_counter
    _var_id_counter += 1
    return f"{base}_{_var_id_counter}"


def standardize_apart(clause: Clause) -> Clause:
    # replace variables in clause with fresh ones
    var_map: Dict[str, Variable] = {}
    def fresh_term(t: Term) -> Term:
        if isinstance(t, Variable):
            if t.name not in var_map:
                var_map[t.name] = Variable(fresh_var_name(t.name))
            return var_map[t.name]
        return t
    head = Literal(fresh_term(clause.head.subject), clause.head.verb, fresh_term(clause.head.object))
    body = [Literal(fresh_term(b.subject), b.verb, fresh_term(b.object)) for b in clause.body]
    return Clause(head, body)

# -----------------------------
# Simple REPL + sample KB
# -----------------------------

SAMPLE_KB_TEXT = '''
john likes mary.
mary likes alice.
alice likes bob.
bob likes carol.
alice parent_of carol.
carol parent_of dave.
dave owns "green_bike".
bookstore sells "logic_book".

X loves Y if X likes Y, Y likes X.
X grandparent_of Z if X parent_of Y, Y parent_of Z.
X indirectly_likes Z if X likes Y, Y indirectly_likes Z.
X acquainted_with Y if X knows Y, Y knows X.
Person buyer_of Item if Person buys Item, Person pays_for Item.
'''


def parse_kb(text: str) -> KB:
    toks = simple_tokenize(text)
    p = Parser(toks)
    clauses = p.parse_program()
    return KB(clauses)


def parse_query(text: str) -> Literal:
    toks = simple_tokenize(text)
    p = Parser(toks)
    # allow single literal terminated by dot
    lit = p.parse_literal()
    # optional DOT consumption
    return lit


def repl(kb: KB):
    print("SVO Logic REPL. Type queries like: ?- X likes mary.")
    print("Type 'exit' to quit. Type 'show kb' to print loaded clauses.")
    while True:
        try:
            line = input('?- ')
        except EOFError:
            print(); break
        if not line.strip():
            continue
        if line.strip() == 'exit':
            break
        if line.strip() == 'show kb':
            for c in kb.clauses:
                print('  ', clause_to_str(c))
            continue
        # allow queries optionally prefixed with '?-'
        if line.strip().startswith('?-'):
            qtext = line.strip()[2:].strip()
        else:
            qtext = line.strip()
        if not qtext.endswith('.'):
            qtext += '.'
        try:
            qlit = parse_query(qtext)
        except Exception as e:
            print('Parse error:', e)
            continue
        # run solver
        sol_count = 0
        for sol, trace in solve(kb, [qlit]):
            sol_count += 1
            print(f"Solution #{sol_count}:")
            # print substitution mapping for user variables present in query
            qvars = [v.name for v in collect_variables(qlit)]
            for var in qvars:
                if var in sol:
                    print(f"  {var} = {term_to_readable(sol[var])}")
            print('Proof trace:')
            for step in trace:
                print('  ', clause_to_str(step.clause), 'unifier=', {k: term_to_readable(v) for k,v in step.subst.items()})
            print('')
        if sol_count == 0:
            print('No solutions.')

# -----------------------------
# Helpers
# -----------------------------

def collect_variables(l: Literal) -> List[Variable]:
    vars: List[Variable] = []
    def maybe_add(t: Term):
        if isinstance(t, Variable):
            vars.append(t)
    maybe_add(l.subject)
    maybe_add(l.object)
    return vars

def term_to_readable(t: Term) -> str:
    if isinstance(t, Atom):
        return t.name
    if isinstance(t, Variable):
        return t.name
    return str(t)

# -----------------------------
# Unit tests
# -----------------------------

class TestParser(unittest.TestCase):
    def test_fact_parse(self):
        toks = simple_tokenize('john likes mary.')
        p = Parser(toks)
        clauses = p.parse_program()
        self.assertEqual(len(clauses), 1)
        cl = clauses[0]
        self.assertTrue(cl.is_fact())
        self.assertIsInstance(cl.head.subject, Atom)
        self.assertEqual(cl.head.verb.name, 'likes')
        self.assertIsInstance(cl.head.object, Atom)
    def test_rule_parse(self):
        toks = simple_tokenize('X ancestor_of Z if X parent_of Y, Y parent_of Z.')
        p = Parser(toks)
        clauses = p.parse_program()
        self.assertEqual(len(clauses), 1)
        cl = clauses[0]
        self.assertFalse(cl.is_fact())
        self.assertIsInstance(cl.head.subject, Variable)
        self.assertIsInstance(cl.head.object, Variable)
        self.assertEqual(len(cl.body), 2)

class TestUnifySolve(unittest.TestCase):
    def setUp(self):
        kb_text = 'john likes mary. mary likes john. X loves Y if X likes Y, Y likes X.'
        self.kb = parse_kb(kb_text)
    def test_unify_fact(self):
        q = parse_query('X loves mary.')
        sols = list(solve(self.kb, [q]))
        # no loves fact directly, but loves rule requires symmetric likes; we have john likes mary and mary likes john, so X=john
        self.assertTrue(any(sol for sol,trace in sols))
        self.assertEqual(term_to_readable(sols[0][0]['X']), 'john')

# Simple manual test runner

def run_tests():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    unittest.TextTestRunner(verbosity=2).run(suite)

# -----------------------------
# Entrypoint
# -----------------------------

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('--test','test'):
        run_tests()
        sys.exit(0)
    kb = parse_kb(SAMPLE_KB_TEXT)
    try:
        repl(kb)
    except KeyboardInterrupt:
        print('\nGoodbye')
