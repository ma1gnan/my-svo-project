# S-V-O Logic Language — Project README

A minimal multi-file Python project implementing an S‑V‑O (Subject‑Verb‑Object) logic language inspired by Prolog but with natural S‑V‑O surface syntax. This repository contains a parser, AST, interpreter (backward chaining solver), CLI, and tests suitable for teaching and prototyping.

Contents

- svo/
  - __init__.py        — package exports
  - lexer.py           — tokenizer (simple_tokenize)
  - ast.py             — Atom, Variable, Literal, Clause + pretty printers
  - parser.py          — recursive-descent parser (parse_kb, parse_query)
  - interpreter.py     — KB, backward-chaining solver, unification, proof traces
- cli.py               — command-line interface and REPL
- tests/
  - test_kb.py         — pytest tests (parsing, simple queries, rules)
- sample_kb.kb         — (optional) example KB text file
- README.md            — this file

Quick start

Requirements

- Python 3.8+
- pytest (for running tests)

Install (recommended: inside a virtualenv)

1. Create venv

   python -m venv .venv
   source .venv/bin/activate    # macOS / Linux
   .\.venv\Scripts\activate   # Windows (PowerShell)

2. Install dev dependency

   pip install -U pip
   pip install pytest

Run the CLI with example KB

   python cli.py --example

This will load a built-in sample KB and drop you into an interactive REPL. Example queries:

   ?- X loves mary.
   ?- X grandparent_of dave.

Load a KB file and run a single query

   python cli.py --kb mykb.kb --query "X likes mary." --max 5

Run tests

   pytest -q

Project layout details

- lexer.simple_tokenize(text) -> List[Token]
  - Friendly tokenizer that recognizes identifiers, quoted strings, numbers, '.', ',', 'if', and '?-'.

- parser.Parser(tokens) -> parse_program() -> List[Clause]
  - Recursive-descent parser that returns Clause and Literal AST nodes.

- ast.py
  - Provides Atom and Variable terms, Literal triples, Clause containers, and pretty-print helpers.

- interpreter.KB(clauses)
  - Build an index by verb name for efficient clause lookup.
  - solve(kb, goals) yields substitutions and proof traces.

Design notes and teaching choices

- Every literal is strictly Subject Verb Object on the surface. Implementations may offer a dummy object for intransitive verbs (e.g., `john sleeps none.`) or extend grammar later to permit optional objects.
- Variables are identified by starting with an uppercase letter or being the underscore `_` (anonymous).
- Quoted strings support spaces and are treated as atoms.
- The interpreter uses depth-first SLD-style backward chaining with standardize-apart variable renaming; it does not implement cuts or negation-as-failure in the current prototype.

Extending the project

- Add built-in predicates for arithmetic and comparisons (e.g., `is`, `>`, `<`).
- Add negation-as-failure (`not/1`) and a cut operator (`!`) with careful semantics.
- Implement WAM-like compilation or convert the interpreter into a more efficient VM for larger KBs.
- Add a web UI (React + TypeScript) to visualize parse trees and proof traces.

Development tips

- Keep the parser and AST simple and well-typed to make teaching easier.
- Use the tests in `tests/test_kb.py` as a regression suite when adding new features.

License

Choose a license appropriate for your project (MIT is a common permissive choice).

Contact / support

If you want me to generate additional project files (packaging, setup.py/pyproject.toml, more tests, CI config, or a web demo), tell me which file(s) to produce next and I will generate them.
