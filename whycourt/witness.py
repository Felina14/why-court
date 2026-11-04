"""The witness stand: where the trial pauses for the child.

`call_witness` is a Strands tool that raises an interrupt. The whole hearing Graph stops, the child's screen shows the
question, and when the child answers, the Graph resumes inside this same tool call with their answer.

Strands re-runs an interrupted tool from the top when it resumes, so everything before `tool_context.interrupt` is a
pure function of the court record: the record only changes after the child has answered.

Two kinds of witness plan:
- "book": for topics in the Rule Book. Each next question is the one that best splits the ideas still in play
  (rulebook.next_question), and the child's answers eliminate ideas.
- "queue": for other topics, the questions the Witness Builder agent found and verified, asked in order.
"""
from __future__ import annotations

from strands import ToolContext, tool

from . import rulebook


def _plan(court: dict) -> dict:
    """Build the witness plan once, the first time a witness is called (deterministic, so safe to rebuild)."""
    if "witness_plan" in court:
        plan = court["witness_plan"]
        if plan["kind"] == "book" and "table" not in plan["state"]:  # resumed from disk: rebuild the exact table
            plan["state"] = rulebook.restore(plan["state"], court.get("case", {}))
        return plan
    case = court.get("case", {})
    if court.get("checkup"):   # a chapter check-up: no homework question, every idea in the book is a suspect
        cu = court["checkup"]
        court["witness_plan"] = {"kind": "book", "state": {**rulebook.open_state(cu["topic"], cu["grade"]),
                                                           "seed": court.get("seed", "")},
                                 "suspects_from": "the whole Rule Book (check-up)"}
        court.setdefault("witness_log", [])
        return court["witness_plan"]
    topic = rulebook.topic_of(case.get("options") or [], case.get("question", ""))
    if topic:
        book = rulebook.entries(topic)
        named = [s for k in ("prosecutor", "defence", "judge") for s in (court.get(k) or {}).get("suspects", []) if s in book]
        suspects, source = (named, "the court's suspects") if named else (list(book), "the whole Rule Book")
        charged = [r for k in ("prosecutor", "judge") for w in [(court.get(k) or {}).get("wrong_idea") or ""]
                   for r in [w if w in book else next((i for i in book if rulebook.RULES[i][1] == w), "")] if r]
        state = {**rulebook.act_out_suspects(topic, suspects, case), "seed": court.get("seed", ""),
                 "charged": sorted(set(charged))}
        plan = {"kind": "book", "state": state, "suspects_from": source}
    else:
        plan = {"kind": "queue", "queue": list(court.get("witnesses") or [])}
    court["witness_plan"] = plan
    court.setdefault("witness_log", [])
    return plan


def pending(court: dict) -> dict | None:
    """The next witness question, with what each idea predicts, or None if the court has heard enough."""
    plan, log = _plan(court), court.get("witness_log", [])
    if plan["kind"] == "book":
        q = rulebook.next_question(plan["state"])
        if not q:
            return None
        alive = plan["state"]["alive"]
        return {"question": q["question"], "options": q["options"], "answer_if_sound": q["picks"][rulebook.SOUND],
                "predictions": {rulebook.RULES[h][1]: p for h, p in q["picks"].items()
                                if h != rulebook.SOUND and h in alive}}
    queue = plan["queue"]
    return dict(queue[len(log)]) if len(log) < len(queue) else None


def hear(court: dict, witness: dict, answer: str, why: str = "") -> None:
    plan = _plan(court)
    if plan["kind"] == "book":
        rulebook.hear_answer(plan["state"], witness["question"], answer)
    court["witness_log"].append({**witness, "answer": answer, **({"why": why} if why else {})})


def proof(court: dict) -> tuple[str, str]:
    """What the child's answers prove: ('misconception_found', the idea), ('cleared', ''), or ('not_proven', '')."""
    plan, log = court.get("witness_plan"), court.get("witness_log") or []
    if not plan or not log:
        return "not_proven", ""
    if plan["kind"] == "book":
        decision, idea_id = rulebook.finding(plan["state"])
        return decision, rulebook.RULES[idea_id][1] if idea_id else ""
    if all(w["answer"] == w["answer_if_sound"] for w in log):
        return "cleared", ""
    ideas = set.intersection(*(set(w["predictions"]) for w in log))
    fits = [i for i in ideas if all(w["answer"] == w["predictions"][i] != w["answer_if_sound"] for w in log)]
    return ("misconception_found", fits[0]) if len(fits) == 1 else ("not_proven", "")


def _table(w: dict) -> str:
    return (f"'{w['question']}' options {w['options']}: correct understanding picks {w['answer_if_sound']}; "
            + "; ".join(f"'{i}' picks {p}" for i, p in w["predictions"].items()))


@tool(context=True)
def call_witness(tool_context: ToolContext = None) -> str:
    """Call the surprise witnesses. The court chooses each question and the child answers it; this returns when
    the court has heard enough, with what the answers prove. Then file your verdict with record_ruling.
    """
    court = tool_context.invocation_state.setdefault("court", {})
    # One call runs the whole witness stand: it pauses (an interrupt) for every question and resumes with the child's
    # answer. Strands re-runs an interrupted tool from the top, and every answer is already in the court record, so
    # each run simply continues with the next unanswered question. (Asking the model to call again after each answer
    # was fragile: a live Examiner once stopped after two answers.)
    while (w := pending(court)) is not None:
        n = len(court.get("witness_log", []))
        answer = tool_context.interrupt(f"witness_{n}", reason={"question": w["question"], "options": w["options"],
                                                                 "answer_if_sound": w["answer_if_sound"],
                                                                 "predictions": w["predictions"]})
        why = ""
        if isinstance(answer, dict):   # the child may also say why (check-up): {"answer": ..., "why": ...}
            answer, why = answer.get("answer", ""), str(answer.get("why") or "")[:500]
        hear(court, w, str(answer).strip(), why)
    n = len(court.get("witness_log", []))
    if not n:
        return "No fair witness question could be found for this case. File your verdict now: not_proven."
    decision, idea = proof(court)
    return (f"The court has heard enough ({n} witness question(s)).\n"
            + "\n".join(f"Q{i + 1}: {_table(x)}. THE CHILD PICKED {x['answer']}"
                        for i, x in enumerate(court["witness_log"]))
            + f"\nWhat the answers prove: {decision}" + (f" - '{idea}'" if idea else "")
            + "\nFile your verdict now with record_ruling.")
