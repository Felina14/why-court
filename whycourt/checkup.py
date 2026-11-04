"""Chapter check-up: find a sneaky idea BEFORE it costs the child marks.

The child picks their grade and a chapter from their textbook (or a topic). The court works out which Rule Book topic
the chapter teaches (from its exercises; if that is not clear, the Topic Finder agent reads the chapter's title and
key rules). Then a Strands Graph runs the Examiner agent at the same witness stand as a trial: each question is an
interrupt raised inside the call_witness tool, the child's answer resumes the Graph, the question chosen is the one
that best splits the wrong ideas still in play, and the CourtRules hook will not let the Examiner name an idea
without proof (look-alikes ruled out). Paused check-ups live in a Strands session, like paused trials.

A found idea goes straight into the practice round and gets a re-hearing; the teacher sees it in their class.
A check-up is stored like a trial, so every one of those works on it unchanged.
"""
from __future__ import annotations

import os
import uuid
from collections import Counter

from strands.multiagent import GraphBuilder
from strands.multiagent.base import Status

from . import agents, rulebook
from .guardrails import screen_child_text
from .hooks import Timekeeper
from .language import normal as language, translate

MESSAGES = {
    "found": "Found it! You were thinking: {idea}. Now let's practise beating it!",
    "clear": "Your thinking held up on every question. Well reasoned!",
    "not_proven": "No verdict yet: your answers didn't all follow one idea. Try again another day!",
}


def topic_for_chapter(book_id: str, chapter_id: str) -> str:
    """Which Rule Book topic a chapter teaches: by its exercises first, then by asking the Topic Finder agent."""
    from . import library
    ch = library.chapter(book_id, chapter_id)
    if not ch:
        return ""
    votes = Counter(t for e in ch.get("exercises") or []
                    if (t := rulebook.topic_of(e.get("options") or [], e.get("text", ""))))
    if votes:
        return votes.most_common(1)[0][0]
    reply = str(agents.topic_finder()(f"Chapter: {ch.get('title', '')}\nKey rules: {ch.get('key_rules', '')[:1500]}"))
    found = [t for t in rulebook.TOPICS if t in reply.lower()]
    return found[0] if len(found) == 1 else ""


def build_checkup(session_id: str):
    """The check-up Graph: the Examiner at the witness stand (the trial's own agent, tool and hooks)."""
    from .court import _session_manager
    b = GraphBuilder()
    b.add_node(agents.examiner(), "examiner")
    b.set_entry_point("examiner")
    b.set_max_node_executions(3)
    b.set_execution_timeout(float(os.getenv("WHYCOURT_TRIAL_TIMEOUT", "600")))
    b.set_node_timeout(float(os.getenv("WHYCOURT_NODE_TIMEOUT", "120")))
    b.set_hook_providers([Timekeeper()])
    b.set_session_manager(_session_manager(session_id))
    return b.build()


def _task(trial: dict) -> str:
    cu = trial["checkup"]
    return (f"Chapter check-up for a grade {cu['grade']} child on '{cu['name']}'. There is no homework question: "
            "the court tests every known wrong idea on this topic. Call call_witness now and keep calling it until it "
            "says the court has heard enough, then file your verdict with record_ruling.")


def start(topic: str, grade: int, player: str = "guest", class_code: str = "", lang: str = "English") -> dict:
    """A new check-up, stored like a trial. Runs its Graph to the first question (an interrupt)."""
    if topic not in rulebook.TOPICS:
        raise ValueError("The court has no check-up for that topic yet.")
    grade = max(3, min(int(grade or 5), 9))
    name = rulebook.TOPICS[topic][0]
    tid = uuid.uuid4().hex[:10]
    court = {"case": {"question": f"Chapter check-up: {name} (grade {grade})", "options": [], "student_answer": "",
                      "student_why": ""}, "checkup": {"topic": topic, "grade": grade}, "seed": tid}
    trial = {"trial_id": tid, "source": "checkup", "player": player, "class_code": class_code, "lang": language(lang),
             "status": "checkup", "transcript": [], "witness_answers": [], "objections": 0, "misconception": None,
             "case": {**court["case"], "subject": rulebook.TOPICS[topic][1]},
             "checkup": {"topic": topic, "grade": grade, "name": name}, "session": f"checkup-{tid}"}
    _run(trial, court, _task(trial))
    return trial


def _run(trial: dict, court: dict, task) -> dict | None:
    """Run (or resume) the check-up Graph. Returns the next question, or None when the Examiner has ruled."""
    try:
        result = build_checkup(trial["session"])(task, invocation_state={"court": court})
    except Exception as e:  # a node timed out etc.: keep what was heard, never crash
        trial["error"], result = f"{type(e).__name__}: {e}", None
    from .court import _public_record
    trial["court_record"] = _public_record(court)   # the big question table is rebuilt exactly when needed
    if result is not None and result.status == Status.INTERRUPTED and result.interrupts:
        w = result.interrupts[0].reason or {}
        trial["pending_interrupts"] = [i.id for i in result.interrupts]
        trial["pending"] = {"question": w.get("question"), "options": w.get("options")}
        return trial["pending"]
    trial["pending_interrupts"], trial["pending"] = [], None
    return None


def question(trial: dict) -> dict | None:
    """The question waiting for the child (in their language; options exactly as the court checks them)."""
    q = trial.get("pending")
    return {"question": translate(q["question"], trial.get("lang", "English")), "options": q["options"]} if q else None


def answer(trial: dict, given: str, why: str = "") -> dict:
    """The child answered: resume the Graph inside call_witness. Return the next question, or the result."""
    if not trial.get("pending_interrupts"):
        raise KeyError("no question pending")
    why, _ = screen_child_text(why or "")
    given = given.strip()
    trial["witness_answers"].append(given)
    trial.setdefault("checkup_whys", []).append(why)      # the teacher sees the child's own reasons
    court = trial["court_record"]
    responses = [{"interruptResponse": {"interruptId": i, "response": {"answer": given, "why": why}}}
                 for i in trial["pending_interrupts"]]
    if _run(trial, court, responses):
        return {"question": question(trial), "n": len(trial["witness_answers"]) + 1}
    verdict = (court.get("examiner") or {})
    decision = verdict.get("decision", "not_proven")
    lang = trial.get("lang", "English")
    if decision == "misconception_found":
        trial["status"], trial["misconception"] = "misconception_found", verdict.get("wrong_idea")
        result, idea = "found", verdict.get("wrong_idea")
    elif decision == "cleared":
        trial["status"], result, idea = "cleared", "clear", None
    else:
        trial["status"], result, idea = "case_closed", "not_proven", None
    from . import lessons
    rid = lessons.idea_id(idea) if idea else ""
    if rid:
        trial["idea_child"] = translate(lessons.CHILD_IDEA[rid], lang)
    msg = MESSAGES[result].format(idea=lessons.CHILD_IDEA.get(rid, idea or ""))
    info = lessons.insight(trial, {"found": "misconception_found", "clear": "cleared"}.get(result, "not_proven"), rid,
                           lesson_shown=False)
    insight = {k: ([translate(p, lang) for p in v] if isinstance(v, list) else v if k == "next" else translate(v, lang))
               for k, v in info.items()} if info else None
    trial["insight"] = insight
    return {"done": True, "result": result, "message": translate(msg, lang),
            "idea": translate(lessons.CHILD_IDEA.get(rid, idea or ""), lang) if idea else None,
            "practice": result == "found", "insight": insight}
