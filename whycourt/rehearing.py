"""Re-hearing day: did the wrong idea go away?

When the court proves a child holds a Rule Book idea, it books a re-hearing (WHYCOURT_REHEAR_DAYS later, default 7).
On re-hearing day the child answers two fresh questions on which that idea and correct understanding disagree.
Both right: the idea is gone ("fixed"). Both the way the idea predicts: it is still there. Otherwise: mixed.

This is the court's measure of learning, not just of detection: the teacher sees how many caught ideas were fixed.
Every prediction is acted out in the sandbox, exactly like a trial.
"""
from __future__ import annotations

import os
import random
import time
import uuid

from . import rulebook, store
from .sandbox import CANNOT_TELL, act_out_batch

QUESTIONS = 2


def _days() -> float:
    return float(os.getenv("WHYCOURT_REHEAR_DAYS", "7"))


def idea_id(text: str | None) -> str:
    return next((rid for rid, r in rulebook.RULES.items() if r[1] == text), "")


def schedule(trial: dict) -> dict | None:
    """Book a re-hearing for a proven Rule Book idea (once per trial). Returns the booking or None."""
    rid = idea_id(trial.get("misconception"))
    if trial.get("status") != "misconception_found" or not rid or trial.get("rehearing_id"):
        return None
    topic = rulebook.RULES[rid][0]
    asked = {w.get("question") for w in (trial.get("court_record") or {}).get("witness_log", [])}
    bank = [q for q in rulebook._bank(topic) if q["question"] not in asked]
    picks = act_out_batch({"SOUND": rulebook.SOUND_CODES[topic], rid: rulebook.RULES[rid][3]}, bank)
    apart = [q for q in bank if picks[rid][q["question"]] not in (picks["SOUND"][q["question"]], CANNOT_TELL)
             and not picks[rid][q["question"]].startswith("could not run")]
    chosen = random.Random(trial["trial_id"]).sample(apart, min(QUESTIONS, len(apart)))
    if not chosen:
        return None
    booking = {"id": uuid.uuid4().hex[:10], "trial_id": trial["trial_id"], "player": trial.get("player", "guest"),
               "idea_id": rid, "idea": rulebook.RULES[rid][1], "lang": trial.get("lang", "English"),
               "due_at": time.time() + _days() * 86400, "done": False,
               "questions": [{"question": q["question"], "options": q["options"],
                              "correct": picks["SOUND"][q["question"]], "idea_pick": picks[rid][q["question"]]}
                             for q in chosen]}
    store.save_rehearing(booking)
    trial["rehearing_id"] = booking["id"]
    if booking["lang"] != "English":  # translate now, in the background, so re-hearing day opens instantly
        import threading
        from .language import translate
        lines = [booking["idea"], *(q["question"] for q in booking["questions"]), *MESSAGES.values()]
        threading.Thread(target=lambda: [translate(x, booking["lang"]) for x in lines], daemon=True).start()
    return booking


def due(player: str) -> list[dict]:
    """Re-hearings this player can take now. The child never sees which answer is correct."""
    now = time.time()
    from .language import translate
    return [{"id": r["id"], "idea": translate(r["idea"], r.get("lang", "English")),
             "questions": [{"question": translate(q["question"], r.get("lang", "English")), "options": q["options"]}
                           for q in r["questions"]]}
            for r in store.player_rehearings(player) if not r["done"] and r["due_at"] <= now]


MESSAGES = {
    "fixed": "Case dismissed for good! You beat the sneaky idea: your thinking held up on every question.",
    "still_there": "The sneaky idea is still hiding. That's okay: let's practise it together now.",
    "mixed": "Half and half! You're getting there. One more practice and the sneaky idea is gone.",
}


def answer(rehearing_id: str, answers: list[str]) -> dict:
    r = store.get_rehearing(rehearing_id)
    if not r or r["done"]:
        raise KeyError(rehearing_id)
    answers = [str(a).strip() for a in answers][:len(r["questions"])]
    right = sum(a == q["correct"] for a, q in zip(answers, r["questions"]))
    idea = sum(a == q["idea_pick"] for a, q in zip(answers, r["questions"]))
    n = len(r["questions"])
    result = "fixed" if right == n and len(answers) == n else "still_there" if idea == n else "mixed"
    r.update({"done": True, "answers": answers, "result": result, "answered_at": time.time()})
    store.save_rehearing(r)
    from .language import translate
    lang = r.get("lang", "English")
    return {"result": result, "message": translate(MESSAGES[result], lang), "idea": translate(r["idea"], lang),
            "trial_id": r["trial_id"], "practice": result != "fixed"}   # not gone yet: straight into practice


def summary(trials: list[dict] | None = None) -> dict:
    """Re-hearing results, optionally only for these trials (one class)."""
    mine = store.all_rehearings() if trials is None else store.rehearings_of(trials)
    done = [r for r in mine if r["done"]]
    return {"booked": len(mine), "done": len(done), "fixed": sum(r["result"] == "fixed" for r in done),
            "still_there": sum(r["result"] == "still_there" for r in done)}
