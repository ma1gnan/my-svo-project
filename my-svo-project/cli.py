"""
Command-line interface for the S-V-O logic language project.

Usage examples:
  python cli.py --kb sample.kb            # start REPL with KB loaded
  python cli.py --kb sample.kb --query "X grandparent_of dave." --max 5
  python cli.py --example                 # run built-in sample KB and drop to REPL

This script expects the package modules to be importable as `svo.parser`,
`svo.interpreter`, and `svo.ast` (the project layout produced earlier).
"""
import argparse
import sys
from typing import List

from svo.parser import parse_kb, parse_query
from svo.interpreter import KB, solve, term_to_readable, collect_variables
from svo.ast import clause_to_str, literal_to_str


SAMPLE_KB = '''
john likes mary.
mary likes john.
alice parent_of carol.
carol parent_of dave.

X loves Y if X likes Y, Y likes X.
X grandparent_of Z if X parent_of Y, Y parent_of Z.
'''


def load_kb_file(path: str) -> KB:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    clauses = parse_kb(text)
    kb = KB(clauses)
    return kb


def run_query(kb: KB, query_text: str, max_solutions: int = 10) -> List[dict]:
    # ensure query_text ends with a period
    qt = query_text.strip()
    if qt.startswith('?-'):
        qt = qt[2:].strip()
    if not qt.endswith('.'):
        qt = qt + '.'
    lit = parse_query(qt)
    solutions = []
    for i, (subst, trace) in enumerate(solve(kb, [lit])):
        if i >= max_solutions:
            break
        # build readable solution mapping for variables present in query
        vars_in_query = [v.name for v in collect_variables(lit)]
        sol_readable = {v: term_to_readable(subst[v]) for v in vars_in_query if v in subst}
        solutions.append({'subst': subst, 'readable': sol_readable, 'trace': trace})
    return solutions


def print_solution(sol_idx: int, sol: dict):
    print(f"Solution #{sol_idx}:")
    if sol['readable']:
        for k, v in sol['readable'].items():
            print(f"  {k} = {v}")
    else:
        print("  (no variable bindings)")
    print('Proof trace:')
    for step in sol['trace']:
        print('  - goal:   ', literal_to_str(step.goal))
        print('    clause: ', clause_to_str(step.clause))
        if step.subst:
            pretty = {k: term_to_readable(v) for k, v in step.subst.items()}
            print('    unifier:', pretty)
    print('')


def repl(kb: KB):
    print("S-V-O Logic REPL. Enter queries like: ?- X loves mary.")
    print("Commands: 'show kb', 'exit', or just enter a query (with or without '?-').")
    while True:
        try:
            line = input('?- ')
        except EOFError:
            print(); break
        if not line.strip():
            continue
        cmd = line.strip()
        if cmd == 'exit':
            break
        if cmd == 'show kb':
            for c in kb.clauses:
                print('  ', clause_to_str(c))
            continue
        # otherwise treat as query
        try:
            sols = run_query(kb, cmd, max_solutions=10)
        except Exception as e:
            print('Error parsing or running query:', e)
            continue
        if not sols:
            print('No solutions.')
            continue
        for idx, s in enumerate(sols, start=1):
            print_solution(idx, s)


def main(argv=None):
    p = argparse.ArgumentParser(description='S-V-O Logic CLI')
    p.add_argument('--kb', '-k', help='Path to KB file to load')
    p.add_argument('--query', '-q', help='Single query to run (e.g. "X loves mary.")')
    p.add_argument('--max', '-m', type=int, default=10, help='Max solutions to show for a query')
    p.add_argument('--example', action='store_true', help='Use built-in example KB and start REPL')
    args = p.parse_args(argv)

    if args.example:
        clauses = parse_kb(SAMPLE_KB)
        kb = KB(clauses)
        if args.query:
            sols = run_query(kb, args.query, args.max)
            if not sols:
                print('No solutions.')
            else:
                for i, s in enumerate(sols, start=1):
                    print_solution(i, s)
            return
        repl(kb)
        return

    if args.kb:
        try:
            kb = load_kb_file(args.kb)
        except Exception as e:
            print('Failed to load KB:', e)
            return
    else:
        print('No KB specified. Use --kb PATH or --example to run with sample KB.')
        return

    if args.query:
        sols = run_query(kb, args.query, args.max)
        if not sols:
            print('No solutions.')
        else:
            for i, s in enumerate(sols, start=1):
                print_solution(i, s)
        return

    # no single query: start interactive REPL
    repl(kb)


if __name__ == '__main__':
    main()
