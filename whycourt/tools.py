"""Tools the court's agents can choose to call. No misconception logic lives here.

- calculate: exact arithmetic and comparisons with fractions and decimals (a calculator, nothing more).
- record_ruling / record_witnesses: how an agent files its decision into the shared court record
  (Strands invocation_state), which the Graph's edges then read.
"""
from __future__ import annotations

import ast
import json
import operator as op
import re
from typing import Literal
from fractions import Fraction

from strands import ToolContext, tool

from .sandbox import CANNOT_TELL

_BIN = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv}
_CMP = {ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge, ast.Eq: op.eq, ast.NotEq: op.ne}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.Compare):
        left = _eval(node.left)
        for o, comp in zip(node.ops, node.comparators):
            right = _eval(comp)
            if type(o) not in _CMP or not _CMP[type(o)](left, right):
                return False
            left = right
        return True
    raise ValueError("only numbers, + - * /, and comparisons are allowed")


def calculate_expr(expression: str) -> str:
    tree = ast.parse(expression.replace("×", "*").replace("÷", "/"), mode="eval")
    v = _eval(tree)
    if isinstance(v, bool):
        return f"{expression} is {v}"
    return f"{expression} = {v} (exactly), about {float(v):.4g}"


@tool
def calculate(expression: str) -> str:
    """Exact calculator for fractions and decimals. Use it to check any number fact before relying on it.

    Args:
        expression: e.g. "3/5 > 2/4", "0.45 - 0.4", "-12 > -15", "7/10 < 3/5"
    """
    try:
        return calculate_expr(expression)
    except Exception as e:  # tell the agent, don't crash the trial
        return f"Could not calculate '{expression}': {e}"


def _court(tool_context: ToolContext) -> dict:
    return tool_context.invocation_state.setdefault("court", {})


BUDGET = {"act_out": 3, "record_witnesses": 2}   # verify_witness: budget kept by the CourtRules hook


def over_budget(tool_context: ToolContext, name: str) -> str:
    """Tool-call budget, so an agent cannot loop until it times out. Returns a message if the budget is used up."""
    used = _court(tool_context).setdefault("tool_calls", {})
    used[name] = used.get(name, 0) + 1
    if used[name] > BUDGET[name]:
        return (f"{name} budget used up ({BUDGET[name]} calls). Do not call it again. "
                "Call record_witnesses with your best questions now, or stop and the court will rule 'not proven'.")
    return ""


# Each court member may only file the decisions its role allows; the Graph's edges read exactly these words.
# (A free-text ruling like "Cross-examine" used to make an edge fail silently.)
DECISIONS = {
    "usher": ("has_claim", "no_claim"), "clerk": ("trial", "wrong_answer"), "prosecutor": ("charge", "no_case"),
    "defence": ("sound", "doubtful"), "judge": ("cross_examine", "case_closed"),
    "examiner": ("misconception_found", "cleared", "not_proven"),
}
Decision = Literal["has_claim", "no_claim", "trial", "wrong_answer", "charge", "no_case", "sound", "doubtful",
                   "cross_examine", "case_closed", "misconception_found", "cleared", "not_proven"]


@tool(context=True)
def record_ruling(decision: Decision, statement: str, wrong_idea: str = "", evidence: str = "",
                  suspects: list[str] | None = None, tool_context: ToolContext = None) -> str:
    """File your decision in the court record. Call this exactly once, at the end of your turn.

    Args:
        decision: your decision word, exactly as your instructions list it
        statement: what you say aloud to the child, one or two kind sentences
        wrong_idea: the wrong idea in plain words, if your decision is about one
        evidence: the child's exact words you rely on, if any
        suspects: ids of the Rule Book ideas you suspect, if the case shows the court's Rule Book
    """
    role = tool_context.agent.name
    decision = re.sub(r"[\s-]+", "_", str(decision).strip().lower())
    allowed = DECISIONS.get(role)
    if allowed and decision not in allowed:
        return f"Not filed: '{decision}' is not a decision you can make. File exactly one of: {', '.join(allowed)}."
    _court(tool_context)[role] = {"decision": decision, "statement": statement,
                                  "wrong_idea": wrong_idea, "evidence": evidence,
                                  "suspects": [str(x).strip() for x in (suspects or [])]}
    return f"Recorded {role}: {decision}"


@tool(context=True)
def record_reteach(title: str, explanation: str, try_this: str, try_this_answer: str,
                   tool_context: ToolContext = None) -> str:
    """File the lesson the child sees after a wrong idea is found. Call once, after the Maths Expert checked it.

    Args:
        title: fun "community service" title, e.g. "Pizza Patrol"
        explanation: at most 3 short sentences (50 words) teaching the right idea with one everyday example
        try_this: one new practice question where the wrong idea gives the wrong answer
        try_this_answer: its correct answer
    """
    _court(tool_context)["reteach"] = {"title": title, "explanation": explanation, "try_this": try_this,
                                       "try_this_answer": try_this_answer}
    return "Lesson filed."


@tool(context=True)
def act_out(rules: dict, questions: list[dict], tool_context: ToolContext = None) -> str:
    """Act out how children think by RUNNING each idea as a rule on every question. Send MANY questions at once.

    Each rule is Python: def pick(question, options): ... return one of the options.
    Apply the idea literally, the way a child who believes it would. Helpers: num("3/5") exact value,
    top("3/5")=3, bottom("3/5")=5, digits_after_point("0.45")="45", words(text),
    calculate("3/5 > 2/4")=True. No imports.
    Every rule is run twice, with the options in both orders. A rule that answers differently depending on the
    order is not deciding, it is tying, and the answer comes back as "cannot tell".

    Args:
        rules: {idea in plain words: pick code}. Include "SOUND" for correct understanding.
        questions: [{"question": str, "options": [str, ...]}]. Include the ORIGINAL question and as many
                   candidate witness questions as you can think of - 15 or 20 is normal and cheap.
    """
    from .sandbox import act_out_batch
    if (msg := over_budget(tool_context, "act_out")):
        return msg
    court = _court(tool_context)
    sims = court.setdefault("simulations", [])
    qs = [{"question": str(q.get("question", "")).strip(), "options": list(q.get("options", []))}
          for q in questions if str(q.get("question", "")).strip() and len(q.get("options", [])) >= 2]
    if not qs:
        return "No usable questions: each needs a question and at least 2 options."
    picks = act_out_batch(dict(rules), qs)
    for q in qs:
        for idea in rules:
            sims.append({"idea": idea.strip(), "code": rules[idea], "question": q["question"],
                         "options": q["options"], "pick": picks[idea][q["question"]]})

    # Report it as a table, and say plainly which questions would work as a witness.
    ideas = [i for i in rules if i.strip() != "SOUND"]
    lines = [f"Ran {len(rules)} rule(s) over {len(qs)} question(s).", ""]
    usable = []
    for q in qs:
        sound = picks.get("SOUND", {}).get(q["question"], "?")
        bits = [f"SOUND={sound}"] + [f"{i!r}={picks[i][q['question']]}" for i in ideas]
        splits = [i for i in ideas if picks[i][q["question"]] not in (sound, CANNOT_TELL)
                  and not picks[i][q["question"]].startswith("could not run")]
        if splits and len(splits) == len(ideas):
            usable.append(q["question"])
        lines.append(f"{'USABLE  ' if q['question'] in usable else '        '}{q['question']}  ->  " + ", ".join(bits))
    lines.append("")
    lines.append(f"{len(usable)} question(s) separate every idea from SOUND: {usable}" if usable else
                 "No question separates every idea from SOUND yet. Most candidates fail - that is normal. "
                 "Send another batch of 15-20 candidates, choosing items where the idea and the correct rule "
                 "point in OPPOSITE directions.")
    return "\n".join(lines)


@tool(context=True)
def book_questions(tool_context: ToolContext = None) -> str:
    """Real questions from the child's own textbook chapter, free candidates for the surprise witness.

    Returns nothing if this case did not come from the Law Library.
    """
    court = _court(tool_context)
    case = court.get("case", {})
    if not case.get("book_id") or not case.get("chapter_id"):
        return "This case is not from a textbook chapter, so there are no book questions. Write your own candidates."
    try:
        from . import library
        ch = library.chapter(case["book_id"], case["chapter_id"])
    except Exception as e:
        return f"Could not open the chapter: {e}"
    out = [{"question": e["text"], "options": e.get("options") or [], "answer_key": e.get("answer")}
           for e in ch.get("exercises", [])
           if len(e.get("options") or []) >= 2 and e["text"].strip() != case.get("question", "").strip()]
    if not out:
        return "This chapter has no multiple-choice exercises to borrow. Write your own candidates."
    return (f"{len(out)} question(s) from '{ch.get('book_title', '')}' chapter {ch.get('number', '')}. "
            f"Put them in act_out alongside your own candidates:\n" + json.dumps(out, ensure_ascii=False))


def _latest(sims, idea, question):
    found = [x for x in sims if x["idea"] == idea and x["question"] == question.strip()]
    return found[-1]["pick"] if found else None


@tool(context=True)
def record_witnesses(questions: list, tool_context: ToolContext = None) -> str:
    """File the surprise witness questions. Call once, after acting out every rule on them and verify_witness.

    The court fills in the predictions from your act_out runs, so only list the questions and their answer keys.

    Args:
        questions: 1 or 2 items {"question": exactly as you acted it out, "answer_key": the correct option,
                   checked with calculate for numbers}
    """
    if (msg := over_budget(tool_context, "record_witnesses")):
        return msg
    court = _court(tool_context)
    sims, case = court.get("simulations", []), court.get("case", {})
    original = case.get("question", "").strip()
    sound_ok = _latest(sims, "SOUND", original) in (case.get("correct_answer"), None) if case.get("correct_answer") else True
    # A wrong idea counts only if acting it out on the ORIGINAL question reproduces the child's actual answer.
    ideas = sorted({x["idea"] for x in sims if x["idea"] != "SOUND"
                    and _latest(sims, x["idea"], original) == case.get("student_answer")})
    verified = {v["question"].strip(): v["report"].lower() for v in court.get("verifications", [])}
    kept, why_not = [], []
    for item in questions[:2]:
        q, key = (item.get("question", ""), item.get("answer_key")) if isinstance(item, dict) else (item, None)
        q = str(q).strip()
        sound = _latest(sims, "SOUND", q)
        preds = {i: _latest(sims, i, q) for i in ideas}
        rep = verified.get(q, "")
        if not sound_ok:
            why_not.append(f"{q!r}: your SOUND rule does not give the answer key on the original question")
        elif not ideas:
            why_not.append("no wrong idea reproduces the child's answer on the original question: act them out there first")
        elif sound is None or any(p is None for p in preds.values()):
            why_not.append(f"{q!r}: act out SOUND and every idea ({ideas}) on it first")
        elif sound == CANNOT_TELL or any(p == CANNOT_TELL for p in preds.values()):
            stuck = [i for i, p in preds.items() if p == CANNOT_TELL] + (["SOUND"] if sound == CANNOT_TELL else [])
            why_not.append(f"{q!r}: {stuck} cannot decide it (the options tie), so it would prove nothing")
        elif key is not None and str(key).strip().lower() != str(sound).strip().lower():
            why_not.append(f"{q!r}: your SOUND rule picks {sound} but the answer key is {key}: fix SOUND")
        elif any(p == sound for p in preds.values()):
            why_not.append(f"{q!r}: some ideas pick the same as SOUND {preds}, so it cannot tell them apart")
        elif "fair: yes" not in rep or "faithful: no" in rep:
            why_not.append(f"{q!r}: the Verifier has not passed it (needs FAIR: yes and no FAITHFUL: no)")
        else:
            opts = next(x["options"] for x in reversed(sims) if x["question"] == q)
            kept.append({"question": q, "options": opts, "answer_if_sound": sound, "predictions": preds})
    if not kept:
        return "Refused. " + " | ".join(why_not) + " Fix this, then call record_witnesses again."
    court["witnesses"] = kept
    return f"Recorded {len(kept)} witness question(s)." + (f" Not kept: {' | '.join(why_not)}" if why_not else "")
