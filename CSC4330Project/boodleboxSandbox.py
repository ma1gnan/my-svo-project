"""
Tiny sandboxed interpreter with lexical/dynamic scoping toggle,
step execution, stop control, and environment-chain inspection.

No use of eval/exec; AST is constructed directly in Python.

Author: generated for a student exercise
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import unittest

# -----------------------
# AST Node Definitions
# -----------------------

class Stmt: pass
class Expr: pass

@dataclass
class Program:
    stmts: List[Stmt]

@dataclass
class FunctionDef(Stmt):
    name: str
    params: List[str]
    body: List[Stmt]

@dataclass
class VarDecl(Stmt):
    name: str
    expr: Optional[Expr]  # initializer optional

@dataclass
class Assign(Stmt):
    name: str
    expr: Expr

@dataclass
class Return(Stmt):
    expr: Optional[Expr]

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class Print(Stmt):
    expr: Expr

@dataclass
class Block(Stmt):
    stmts: List[Stmt]

# Expressions
@dataclass
class Literal(Expr):
    value: Any

@dataclass
class VarRef(Expr):
    name: str

@dataclass
class BinaryOp(Expr):
    left: Expr
    op: str
    right: Expr

@dataclass
class CallExpr(Expr):
    callee: Expr
    args: List[Expr]

@dataclass
class VarCall(Expr):  # syntactic sugar: call by name (function stored in var)
    name: str
    args: List[Expr]

# -----------------------
# Runtime structures
# -----------------------

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class StopExecution(Exception):
    pass

class Frame:
    def __init__(self, name: str = "<frame>", parent: Optional["Frame"] = None):
        self.name = name
        self.vars: Dict[str, Any] = {}
        self.parent = parent

    def lookup(self, name: str) -> Optional["Frame"]:
        # Find the frame that defines name in lexical chain
        f = self
        while f is not None:
            if name in f.vars:
                return f
            f = f.parent
        return None

    def chain(self) -> List["Frame"]:
        # Return chain from this frame outward
        frames = []
        f = self
        while f is not None:
            frames.append(f)
            f = f.parent
        return frames

# Function value representation
@dataclass
class FunctionValue:
    name: str
    params: List[str]
    body: List[Stmt]
    defining_frame: Optional[Frame]  # for lexical scoping; None if none

# -----------------------
# Interpreter
# -----------------------

class TinyInterpreter:
    def __init__(self, scoping: str = "lexical"):
        assert scoping in ("lexical", "dynamic")
        self.scoping = scoping
        self.global_frame = Frame("<global>", None)
        self.call_stack: List[Frame] = []  # actual active frames (top = last)
        self._stop_flag = False
        self.output_log: List[str] = []  # capture printed output

    # Public control
    def stop(self):
        self._stop_flag = True

    def reset_stop(self):
        self._stop_flag = False

    # Utility to create a fresh frame for calls
    def _make_call_frame(self, name: str, parent_for_lexical: Optional[Frame] = None):
        if self.scoping == "lexical":
            parent = parent_for_lexical or self.global_frame
        else:  # dynamic
            parent = self.call_stack[-1] if self.call_stack else self.global_frame
        return Frame(name, parent)

    # Environment chain extraction for debugging/displaying:
    def env_chain(self) -> List[Dict[str, Any]]:
        # Return list of frames from top-most (current) to global
        if self.call_stack:
            top = self.call_stack[-1]
        else:
            top = self.global_frame
        chain = []
        f = top
        while f is not None:
            chain.append({"frame": f.name, "vars": dict(f.vars)})
            f = f.parent
        return chain

    # Stepper: yields after each executed statement with snapshot (stmt, env_chain)
    def run_stepwise(self, program: Program):
        # Execute program statements one by one, yield after each top-level statement
        try:
            for stmt in program.stmts:
                if self._stop_flag:
                    raise StopExecution()
                yield from self._exec_stmt_stepwise(stmt, self.global_frame)
        except StopExecution:
            return

    # Internal exec methods (stepwise generators)
    def _exec_stmt_stepwise(self, stmt: Stmt, current_frame: Frame):
        # Many statements yield one snapshot after performing their action
        if isinstance(stmt, FunctionDef):
            # Define function in current frame; store FunctionValue with defining environment
            func_val = FunctionValue(stmt.name, stmt.params, stmt.body,
                                     defining_frame=(current_frame if self.scoping == "lexical" else None))
            current_frame.vars[stmt.name] = func_val
            yield ("define_function", stmt.name, self.env_chain())
        elif isinstance(stmt, VarDecl):
            val = None
            if stmt.expr is not None:
                val = self._eval_expr(stmt.expr, current_frame)
            current_frame.vars[stmt.name] = val
            yield ("var_decl", stmt.name, self.env_chain())
        elif isinstance(stmt, Assign):
            val = self._eval_expr(stmt.expr, current_frame)
            # assign: find frame according to scoping rules
            target_frame = self._find_frame_for_assign(stmt.name, current_frame)
            if target_frame is None:
                # default to current frame
                current_frame.vars[stmt.name] = val
            else:
                target_frame.vars[stmt.name] = val
            yield ("assign", stmt.name, self.env_chain())
        elif isinstance(stmt, Return):
            val = None
            if stmt.expr is not None:
                val = self._eval_expr(stmt.expr, current_frame)
            yield ("return", val, self.env_chain())
            # raise to unwind to caller
            raise ReturnSignal(val)
        elif isinstance(stmt, ExprStmt):
            _ = self._eval_expr(stmt.expr, current_frame)
            yield ("expr", None, self.env_chain())
        elif isinstance(stmt, Print):
            val = self._eval_expr(stmt.expr, current_frame)
            self.output_log.append(str(val))
            yield ("print", val, self.env_chain())
        elif isinstance(stmt, Block):
            # Block: create a new lexical block frame (blocks have lexical nesting)
            block_frame = Frame("<block>", current_frame if self.scoping == "lexical" else current_frame)
            # For dynamic scoping, block parent is still current_frame (dynamic uses call stack for lookup)
            # but we will push/pop only when entering function calls. Blocks are nested via parent pointer.
            for s in stmt.stmts:
                if self._stop_flag:
                    raise StopExecution()
                yield from self._exec_stmt_stepwise(s, block_frame)
        else:
            raise RuntimeError(f"Unknown statement type: {stmt}")

    def _find_frame_for_assign(self, name: str, current_frame: Frame) -> Optional[Frame]:
        if self.scoping == "lexical":
            # find first frame outward containing name
            f = current_frame
            while f is not None:
                if name in f.vars:
                    return f
                f = f.parent
            return None
        else:
            # dynamic: search call stack top-down
            for f in reversed(self.call_stack):
                if name in f.vars:
                    return f
            # finally check global
            if name in self.global_frame.vars:
                return self.global_frame
            return None

    def _eval_expr(self, expr: Expr, current_frame: Frame):
        # Evaluate expression in given current_frame (note: current_frame is where expression is being evaluated)
        if isinstance(expr, Literal):
            return expr.value
        elif isinstance(expr, VarRef):
            # lookup according to scoping rules
            return self._lookup_var(expr.name, current_frame)
        elif isinstance(expr, BinaryOp):
            l = self._eval_expr(expr.left, current_frame)
            r = self._eval_expr(expr.right, current_frame)
            if expr.op == "+":
                return l + r
            elif expr.op == "-":
                return l - r
            elif expr.op == "*":
                return l * r
            elif expr.op == "/":
                return l / r
            else:
                raise RuntimeError("Unknown operator " + expr.op)
        elif isinstance(expr, CallExpr):
            func_val = self._eval_expr(expr.callee, current_frame)
            args = [self._eval_expr(a, current_frame) for a in expr.args]
            return self._call_function(func_val, args, current_frame)
        elif isinstance(expr, VarCall):
            func_val = self._lookup_var(expr.name, current_frame)
            args = [self._eval_expr(a, current_frame) for a in expr.args]
            return self._call_function(func_val, args, current_frame)
        else:
            raise RuntimeError(f"Unknown expression type: {expr}")

    def _lookup_var(self, name: str, current_frame: Frame):
        if self.scoping == "lexical":
            # lexical lookup: follow parent pointers from current frame
            f = current_frame
            while f is not None:
                if name in f.vars:
                    return f.vars[name]
                f = f.parent
            # not found: error
            raise NameError(f"Name '{name}' not found (lexical)")
        else:
            # dynamic: search call stack from top to bottom, then global
            for f in reversed(self.call_stack):
                if name in f.vars:
                    return f.vars[name]
            if name in self.global_frame.vars:
                return self.global_frame.vars[name]
            raise NameError(f"Name '{name}' not found (dynamic)")

    def _call_function(self, func_val: Any, args: List[Any], current_frame: Frame):
        if not isinstance(func_val, FunctionValue):
            raise TypeError("Attempt to call a non-function: " + repr(func_val))
        # Determine parent frame for the new call frame
        if self.scoping == "lexical":
            parent_for_call = func_val.defining_frame or self.global_frame
        else:
            # dynamic: parent is current top-of-call-stack (not the defining env)
            parent_for_call = None  # _make_call_frame will pick call_stack top
        call_frame = self._make_call_frame(func_val.name, parent_for_call)
        # bind parameters
        for p, a in zip(func_val.params, args):
            call_frame.vars[p] = a
        # If function has no closure-defining_frame in lexical mode, parent_for_call will be provided
        # Push to call stack
        self.call_stack.append(call_frame)
        try:
            # Execute body statements stepwise but do not yield here (calls nested yields are not exposed)
            for s in func_val.body:
                if self._stop_flag:
                    raise StopExecution()
                # execute statements inside function body in non-top-level mode
                # we call the non-stepwise execution routine for simplicity
                self._exec_stmt_nonstep(s, call_frame)
            # if no return, return None
            return None
        except ReturnSignal as rs:
            return rs.value
        finally:
            self.call_stack.pop()

    def _exec_stmt_nonstep(self, stmt: Stmt, current_frame: Frame):
        # Non-stepwise execution used inside function calls (keeps code simpler).
        # It follows same semantics as stepwise methods but does not yield.
        if isinstance(stmt, FunctionDef):
            func_val = FunctionValue(stmt.name, stmt.params, stmt.body,
                                     defining_frame=(current_frame if self.scoping == "lexical" else None))
            current_frame.vars[stmt.name] = func_val
        elif isinstance(stmt, VarDecl):
            val = None
            if stmt.expr is not None:
                val = self._eval_expr(stmt.expr, current_frame)
            current_frame.vars[stmt.name] = val
        elif isinstance(stmt, Assign):
            val = self._eval_expr(stmt.expr, current_frame)
            target_frame = self._find_frame_for_assign(stmt.name, current_frame)
            if target_frame is None:
                current_frame.vars[stmt.name] = val
            else:
                target_frame.vars[stmt.name] = val
        elif isinstance(stmt, Return):
            val = None
            if stmt.expr is not None:
                val = self._eval_expr(stmt.expr, current_frame)
            raise ReturnSignal(val)
        elif isinstance(stmt, ExprStmt):
            _ = self._eval_expr(stmt.expr, current_frame)
        elif isinstance(stmt, Print):
            val = self._eval_expr(stmt.expr, current_frame)
            self.output_log.append(str(val))
        elif isinstance(stmt, Block):
            block_frame = Frame("<block>", current_frame if self.scoping == "lexical" else current_frame)
            for s in stmt.stmts:
                if self._stop_flag:
                    raise StopExecution()
                self._exec_stmt_nonstep(s, block_frame)
        else:
            raise RuntimeError(f"Unknown statement type: {stmt}")

# -----------------------
# Example tests
# -----------------------

class TestScopingBehavior(unittest.TestCase):
    def setUp(self):
        pass

    def _make_lexical_vs_dynamic_program(self):
        # Creates AST for:
        # var x = 1;
        # function a() { print(x); }
        # function b() { var x = 2; a(); }
        # b();
        prog = Program([
            VarDecl("x", Literal(1)),
            FunctionDef("a", [], [Print(VarRef("x"))]),
            FunctionDef("b", [], [VarDecl("x", Literal(2)), ExprStmt(VarCall("a", []))]),
            ExprStmt(VarCall("b", []))
        ])
        return prog

    def test_lexical_scoping(self):
        interp = TinyInterpreter(scoping="lexical")
        prog = self._make_lexical_vs_dynamic_program()
        # run stepwise fully
        for _ in interp.run_stepwise(prog):
            pass
        self.assertEqual(interp.output_log, ["1"], "In lexical scoping, a() should print global x=1")

    def test_dynamic_scoping(self):
        interp = TinyInterpreter(scoping="dynamic")
        prog = self._make_lexical_vs_dynamic_program()
        for _ in interp.run_stepwise(prog):
            pass
        self.assertEqual(interp.output_log, ["2"], "In dynamic scoping, a() should see x from caller b -> 2")

    def test_env_chain_snapshot(self):
        # Demonstrate env chain snapshots at key steps
        interp = TinyInterpreter(scoping="lexical")
        prog = self._make_lexical_vs_dynamic_program()
        snapshots = []
        for event in interp.run_stepwise(prog):
            snapshots.append(event)
        # Expect define var x and function defs etc. Inspect one snapshot
        # check that global frame has x and functions after definitions
        final_chain = interp.env_chain()
        self.assertTrue(any(f["frame"] == "<global>" for f in final_chain))
        # ensure x present
        global_frame = final_chain[-1]
        self.assertIn("x", global_frame["vars"])

if __name__ == "__main__":
    # Run tests when executed as script
    unittest.main()