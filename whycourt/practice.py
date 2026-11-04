"""Practice round: guided practice right after a wrong idea is found.

A good tutor does not stop at "here is the right idea". The child practises at once, on questions chosen so the old
wrong idea gives the WRONG answer, and hears straight away whether they were right and why. Three questions, each
acted out in the sandbox like every other prediction, and every "why" is worked out exactly by code (common
denominators, place value, the item's known facts), never written by a model, so it cannot teach something false.

Re-hearing day (a week later) then checks whether the idea stayed gone.
"""
from __future__ import annotations

import random
from math import lcm

from . import rulebook
from .lessons import REMEMBER
from .language import translate
from .sandbox import CANNOT_TELL, act_out_batch

QUESTIONS = 3


def _idea_id(trial: dict) -> str:
    return next((rid for rid, r in rulebook.RULES.items() if r[1] == trial.get("misconception")), "")


def _wants_smaller(question: str) -> bool:
    q = question.lower()
    return "small" in q or "less" in q


def why(topic: str, question: str, options: list[str], correct: str) -> str:
    """One exact sentence saying why the right answer is right."""
    if topic == "fractions" and len(options) == 2:
        # Use the fractions exactly as written: Fraction("5/10") would reduce to 1/2 and give "3/4 = 3/4 and
        # 5/10 = 2/4", which is true but no help to a child.
        parts = [tuple(int(x) for x in o.replace(" ", "").split("/")) for o in options]
        d = lcm(*(b for _, b in parts))
        same = " and ".join(f"{o} = {a * d // b}/{d}" for o, (a, b) in zip(options, parts))
        word = "smaller" if _wants_smaller(question) else "bigger"
        return f"Make the pieces the same size: {same}. So {correct} is {word}."
    if topic == "decimals" and len(options) == 2:
        places = max(len(o.split(".")[1]) for o in options)
        padded = [o.split(".")[0] + "." + o.split(".")[1].ljust(places, "0") for o in options]
        unit = {1: "tenths", 2: "hundredths", 3: "thousandths"}.get(places, "parts")
        parts = " and ".join(f"{o} = {p} ({int(p.split('.')[1])} {unit})" for o, p in zip(options, padded))
        word = "smaller" if _wants_smaller(question) else "bigger"
        return f"Line up the places: {parts}. So {correct} is {word}."
    if topic == "floating":
        other = next(o for o in options if o != correct)
        return (f"{correct[0].upper() + correct[1:]} floats and {other} sinks. What it is made of decides it "
                f"(how heavy it is for its size), not how big it is.")
    if topic == "a_an":
        w = rulebook._blank_word(question)
        note = {"hour": " (the h is silent)", "honest": " (the h is silent)", "university": " (it starts with a 'you' sound)",
                "unicorn": " (it starts with a 'you' sound)", "uniform": " (it starts with a 'you' sound)",
                "european": " (it starts with a 'you' sound)", "one": " (it starts with a 'w' sound)"}.get(w, "")
        sound = "a vowel sound" if rulebook.WORDS.get(w) else "a consonant sound"
        return f"'{w}' starts with {sound}{note}, so we say '{correct} {w}'."
    if topic == "negatives" and len(options) == 2:
        other = next(o for o in options if o != correct)
        return (f"On a number line {correct} is to the right of {other}. With negative numbers, the closer to 0, "
                f"the bigger: {correct} is bigger.")
    if topic == "multiply_divide" and len(options) == 2:
        from .tools import calculate_expr
        sums = " and ".join(calculate_expr(o.replace("×", "*").replace("÷", "/")).split(" (exactly)")[0]
                            .replace("*", "×").replace("/", "÷") for o in options if any(c in o for c in "×÷"))
        return (f"Work it out: {sums}. Multiplying by a number less than 1 makes it smaller, and dividing by a number "
                f"less than 1 makes it bigger. So {correct} is bigger.")
    if topic == "plurals":
        word = next((w for w, p in rulebook.PLURALS.items() if p == correct), "")
        return f"'{word}' is a special word: one {word}, two {correct}." if word else f"The right word is {correct}."
    if topic == "past_tense":
        word = next((w for w, p in rulebook.PAST.items() if p == correct), "")
        return f"'{word}' is a special verb: today I {word}, yesterday I {correct}." if word else f"The right word is {correct}."
    return f"The right answer is {correct}."


def start(trial: dict) -> dict | None:
    """Three practice questions for this trial's proven idea (made once, kept with the trial)."""
    rid = _idea_id(trial)
    if trial.get("status") != "misconception_found" or not rid:
        return None
    if not trial.get("practice"):
        topic = rulebook.RULES[rid][0]
        seen = {w.get("question") for w in (trial.get("court_record") or {}).get("witness_log", [])}
        bank = [q for q in rulebook._bank(topic) if q["question"] not in seen]
        picks = act_out_batch({"SOUND": rulebook.SOUND_CODES[topic], rid: rulebook.RULES[rid][3]}, bank)
        apart = [q for q in bank if picks[rid][q["question"]] not in (picks["SOUND"][q["question"]], CANNOT_TELL)
                 and not picks[rid][q["question"]].startswith("could not run")]
        chosen = random.Random(trial["trial_id"] + "-practice").sample(apart, min(QUESTIONS, len(apart)))
        trial["practice"] = {"topic": topic, "answers": [], "questions": [
            {"question": q["question"], "options": q["options"], "correct": picks["SOUND"][q["question"]],
             "why": why(topic, q["question"], q["options"], picks["SOUND"][q["question"]])} for q in chosen]}
    lang = trial.get("lang", "English")
    p = trial["practice"]
    return {"questions": [{"question": translate(q["question"], lang), "options": q["options"]} for q in p["questions"]],
            "tip": translate("Remember: " + REMEMBER[rid], lang),
            "answered": len(p["answers"])}


def answer(trial: dict, i: int, given: str) -> dict:
    p = trial.get("practice")
    if not p or not 0 <= i < len(p["questions"]):
        raise KeyError(i)
    q = p["questions"][i]
    correct = given.strip() == q["correct"]
    if len(p["answers"]) == i:  # each question counts once, in order
        p["answers"].append({"answer": given.strip(), "correct": correct})
    lang = trial.get("lang", "English")
    reason = why(p.get("topic", ""), q["question"], q["options"], q["correct"])  # worked out fresh, never stale
    return {"correct": correct, "right_answer": q["correct"], "why": translate(reason, lang),
            "score": sum(a["correct"] for a in p["answers"]), "of": len(p["questions"])}


def more(trial: dict, n: int = 2) -> dict:
    """Two more tries after a hard round: fresh questions on which the old idea gives the wrong answer."""
    if not trial.get("practice"):
        if not start(trial):
            raise KeyError("no practice")
    p = trial["practice"]
    rid = _idea_id(trial)
    topic = rulebook.RULES[rid][0]
    seen = {q["question"] for q in p["questions"]} | {w.get("question") for w in
                                                      (trial.get("court_record") or {}).get("witness_log", [])}
    bank = [q for q in rulebook._bank(topic) if q["question"] not in seen]
    picks = act_out_batch({"SOUND": rulebook.SOUND_CODES[topic], rid: rulebook.RULES[rid][3]}, bank)
    apart = [q for q in bank if picks[rid][q["question"]] not in (picks["SOUND"][q["question"]], CANNOT_TELL)
             and not picks[rid][q["question"]].startswith("could not run")]
    apart.sort(key=lambda q: len(q["question"]))
    chosen = random.Random(trial["trial_id"] + f"-more{len(p['questions'])}").sample(apart[:15], min(n, len(apart[:15])))
    start_at = len(p["questions"])
    p["questions"] += [{"question": q["question"], "options": q["options"], "correct": picks["SOUND"][q["question"]],
                        "why": why(topic, q["question"], q["options"], picks["SOUND"][q["question"]])} for q in chosen]
    lang = trial.get("lang", "English")
    return {"start": start_at, "questions": [{"question": translate(q["question"], lang), "options": q["options"]}
                                             for q in p["questions"][start_at:]]}
