"""Run a tiny rule an agent wrote, safely.

An agent writes how a child thinks as a small Python function:

    def pick(question, options):
        return max(options, key=lambda o: top(o))   # "the bigger top number wins"

This module checks the code only uses plain, safe Python (no imports, no files, no dunder tricks), then runs it
in a separate process with a time limit. Helpers: num("3/5") -> exact value, top("3/5") -> 3, bottom("3/5") -> 5,
digits_after_point("0.45") -> "45", words(text) -> list of words,
calculate("3/5 > 2/4") -> True (exact; arithmetic gives the exact value).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

_BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr",
                 "delattr", "input", "breakpoint", "exit", "quit", "help", "memoryview", "type", "object"}

_RUNNER = r"""
import json, sys, re, signal
from fractions import Fraction

# Hard limits for the whole process: memory and CPU time (best effort where the OS supports them).
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (768 * 2**20, 768 * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (40, 40))
except Exception:
    pass

# One rule must not be able to hang the whole batch, so every single call gets its own alarm. The alarm is a
# BaseException, so a rule's own `except Exception` cannot swallow it (and rules may not use try at all).
class Took2Long(BaseException): pass
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(Took2Long("the rule took too long (endless loop?)")))
def num(s):
    s = str(s).strip().replace(" ", "")
    m = re.fullmatch(r"(-?\d+)/(\d+)", s)
    if m: return Fraction(int(m[1]), int(m[2]))
    return Fraction(s)
def top(s): return int(str(s).split("/")[0])
def bottom(s): return int(str(s).split("/")[1])
def digits_after_point(s): return str(s).split(".")[1] if "." in str(s) else ""
def words(t): return re.findall(r"[A-Za-z']+", str(t))
# Agents also have a calculate tool, and often call it inside a rule. Here it gives the exact value (or True/False
# for a comparison) so the rule can use it directly: calculate("3/5 > 2/4") -> True, calculate("1/2 + 1/4") -> 3/4.
import ast as _ast, operator as _op
_CALC_BIN = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv}
_CALC_CMP = {_ast.Gt: _op.gt, _ast.Lt: _op.lt, _ast.GtE: _op.ge, _ast.LtE: _op.le, _ast.Eq: _op.eq, _ast.NotEq: _op.ne}
def _calc(n):
    if isinstance(n, _ast.Expression): return _calc(n.body)
    if isinstance(n, _ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return Fraction(str(n.value))
    if isinstance(n, _ast.UnaryOp) and isinstance(n.op, (_ast.USub, _ast.UAdd)):
        v = _calc(n.operand); return -v if isinstance(n.op, _ast.USub) else v
    if isinstance(n, _ast.BinOp) and type(n.op) in _CALC_BIN:
        return _CALC_BIN[type(n.op)](_calc(n.left), _calc(n.right))
    if isinstance(n, _ast.Compare):
        left = _calc(n.left)
        for o, c in zip(n.ops, n.comparators):
            right = _calc(c)
            if type(o) not in _CALC_CMP or not _CALC_CMP[type(o)](left, right): return False
            left = right
        return True
    raise ValueError("calculate only takes numbers, + - * / and comparisons")
def calculate(e):
    return _calc(_ast.parse(str(e).replace("×", "*").replace("÷", "/"), mode="eval"))
B = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
SAFE = {k: B[k] for k in
        ["len","min","max","abs","sorted","int","float","str","any","all","range","enumerate","zip","sum","round",
         "list","dict","set","tuple","isinstance","bool","reversed","map","filter","ValueError","Exception"]}
HELPERS = {"num": num, "top": top, "bottom": bottom, "digits_after_point": digits_after_point,
           "words": words, "Fraction": Fraction, "calculate": calculate}

data = json.loads(sys.stdin.read())
picks = {}
for idea, code in data["rules"].items():
    env = {"__builtins__": SAFE, **HELPERS}
    try:
        signal.setitimer(signal.ITIMER_REAL, 1.0)     # top-level code is alarmed too, not only pick()
        exec(code, env)
        fn = env["pick"]
    except (Exception, Took2Long) as e:
        picks[idea] = {"__error__": f"{type(e).__name__}: {e}"}
        continue
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    out = {}
    for i, q in enumerate(data["questions"]):
        opts = list(q["options"])
        try:
            signal.setitimer(signal.ITIMER_REAL, 1.0)
            # Run both option orders: a rule that follows the order is not deciding, it is tying.
            a, b = str(fn(q["question"], list(opts))), str(fn(q["question"], list(reversed(opts))))
            out[str(i)] = a if a == b else "__tie__"
        except Took2Long as e:
            out[str(i)] = f"__error__ {e}"
        except Exception as e:
            out[str(i)] = f"__error__ {type(e).__name__}: {e}"
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    picks[idea] = out
print(json.dumps(picks))
"""


def check_code(code: str) -> str:
    """Return '' if the code is safe to run, else the reason it is not."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"syntax error: {e}"
    if not any(isinstance(n, ast.FunctionDef) and n.name == "pick" for n in tree.body):
        return "define a function pick(question, options) that returns one of the options"
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.With, ast.AsyncFunctionDef,
                          ast.Await, ast.Yield, ast.YieldFrom, ast.ClassDef, ast.Try, ast.TryStar)):
            return f"{type(n).__name__} is not allowed"
        if isinstance(n, ast.Attribute) and (n.attr.startswith("_") or n.attr in ("format", "format_map")):
            return f"'.{n.attr}' is not allowed"
        if isinstance(n, ast.Name) and (n.id in _BANNED_NAMES or n.id.startswith("__")):
            return f"'{n.id}' is not allowed"
    return ""


CANNOT_TELL = "cannot tell"


def _run(rules: dict[str, str], questions: list[dict], timeout: float = 60.0) -> tuple[dict, str]:
    """Run every rule over every question in ONE sandboxed process (each call alarmed at 1s inside)."""
    try:
        # A clean environment: the rule code was written by a model that read a child's words, so it must never
        # see AWS credentials or anything else from the server's environment.
        p = subprocess.run([sys.executable, "-I", "-c", _RUNNER],
                           input=json.dumps({"rules": rules, "questions": questions}),
                           capture_output=True, text=True, timeout=timeout,
                           env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",   # Lambda's Python needs its own libraries
                                **{k: os.environ[k] for k in ("LD_LIBRARY_PATH",) if k in os.environ}})
    except subprocess.TimeoutExpired:
        return {}, "the batch took too long"
    if p.returncode != 0:
        return {}, (p.stderr.strip().splitlines() or ["error"])[-1]
    return json.loads(p.stdout), ""


def act_out_batch(rules: dict[str, str], questions: list[dict]) -> dict[str, dict[str, str]]:
    """{idea: {question text: pick}}, where a pick is an option, CANNOT_TELL, or an error message.

    A pick is CANNOT_TELL when the rule answers differently depending on the order the options are given in:
    "the bigger top number wins" simply cannot choose between 1/3 and 1/6, but `max(options, key=top)` quietly
    returns whichever came first. Running both orders turns that hidden tie into a visible one.
    """
    bad = {idea: check_code(code) for idea, code in rules.items()}
    ok = {idea: code for idea, code in rules.items() if not bad[idea]}
    result: dict[str, dict[str, str]] = {idea: {} for idea in rules}
    raw, err = ({}, "") if not ok else _run(ok, questions)
    for idea in rules:
        for q in questions:
            qt = str(q.get("question", "")).strip()
            if bad[idea]:
                result[idea][qt] = f"could not run: {bad[idea]}"
            elif err:
                result[idea][qt] = f"could not run: {err}"
            else:
                pick = (raw.get(idea) or {}).get(str(questions.index(q)), "")
                if isinstance(raw.get(idea), dict) and "__error__" in raw[idea]:
                    pick = f"could not run: {raw[idea]['__error__']}"
                elif pick == "__tie__":
                    pick = CANNOT_TELL
                elif pick.startswith("__error__"):
                    pick = "could not run: " + pick[len("__error__ "):]
                else:
                    match = [o for o in q.get("options", []) if str(o).strip().lower() == pick.strip().lower()]
                    pick = match[0] if match else f"could not run: returned {pick!r}, not one of the options"
                result[idea][qt] = pick
    return result


def act_out_rule(code: str, question: str, options: list[str]) -> tuple[str | None, str]:
    """One rule on one question. Returns (pick or None, error)."""
    out = act_out_batch({"x": code}, [{"question": question, "options": list(options)}])["x"]
    pick = next(iter(out.values()))
    return (None, pick[len("could not run: "):]) if pick.startswith("could not run: ") else (pick, "")
