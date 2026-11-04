"""What the child is told, for every idea in the Rule Book: built from exact templates, never free text.

A student audit found a model-written lesson that stated the wrong idea as the rule ("you've eaten more of the first
pizza because you've eaten more pieces") and another that asked an 8-year-old to compare 20/30 and 22.5/30. For ideas
the court can prove, it now also teaches from exact parts: the idea in a child's own words, a counter-example worked
out by code (practice.why), one "Remember" line, and a "Try this" on which the old idea gives the wrong answer.
"""
from __future__ import annotations

import random

from . import rulebook
from .sandbox import CANNOT_TELL, act_out_batch

# The idea in a child's own words (what the verdict says back to them).
CHILD_IDEA = {
    "top_number": "the bigger top number always wins",
    "bottom_number": "the bigger bottom number always wins",
    "smaller_bottom": "the smaller bottom number always wins",
    "missing_pieces": "fewer missing pieces always wins",
    "whole_number_decimals": "the digits after the point are like a whole number, so 0.45 beats 0.5",
    "shorter_is_larger": "fewer digits after the point means bigger",
    "bigger_digits_negative": "-7 is bigger than -3 because 7 is bigger than 3",
    "multiply_bigger": "times always makes a number bigger, and divide always makes it smaller",
    "big_floats": "big things float and small things sink",
    "small_floats": "small things float and big things sink",
    "light_floats": "light things float and heavy things sink",
    "vowel_letter": "use 'an' before every word that starts with a, e, i, o or u",
    "long_word": "long words take 'an' and short words take 'a'",
    "add_s": "to make more than one, you always just add -s",
    "add_ed": "to talk about the past, you always just add -ed",
}

# The one thing to remember (short, true, for an 8-year-old).
REMEMBER = {
    "top_number": "Look at the whole fraction, not just the top. Make the pieces the same size, then compare.",
    "bottom_number": "More pieces means smaller pieces. Make the pieces the same size, then compare.",
    "smaller_bottom": "Bigger pieces help, but count how many pieces you have too.",
    "missing_pieces": "One missing piece is a lot when pieces are big and a little when they are small. "
                      "Make the pieces the same size, then compare.",
    "whole_number_decimals": "Line up the decimal points and compare tenths first. Adding a zero helps: 0.5 = 0.50.",
    "shorter_is_larger": "Line up the decimal points and add zeros: 0.3 = 0.30, which is less than 0.35.",
    "bigger_digits_negative": "Below zero, the closer to 0, the bigger. -3 is bigger than -7.",
    "multiply_bigger": "Times a number less than 1 makes it smaller. Divide by a number less than 1 makes it bigger.",
    "big_floats": "Floating is about what a thing is made of (how heavy it is for its size), not how big it is.",
    "small_floats": "Floating is about what a thing is made of (how heavy it is for its size), not how big it is.",
    "light_floats": "A big log floats and a tiny coin sinks: what counts is how heavy it is for its size.",
    "vowel_letter": "Listen to the first SOUND, not the first letter: an hour, a unicorn.",
    "long_word": "Length doesn't matter. Listen to the first sound: an ox, a caterpillar.",
    "add_s": "Some words change instead of adding -s: mouse becomes mice, child becomes children.",
    "add_ed": "Some verbs change instead of adding -ed: go becomes went, eat becomes ate.",
}

TITLES = {"fractions": "Fair Slices", "decimals": "Decimal Detective", "negatives": "Below Zero",
          "multiply_divide": "Times and Share", "floating": "Sink or Float", "a_an": "Sound It Out",
          "plurals": "More Than One", "past_tense": "Yesterday Words"}


def idea_id(text: str | None) -> str:
    return next((rid for rid, r in rulebook.RULES.items() if r[1] == text), "")


def _counter_examples(rid: str, avoid: set[str], n: int, seed: str) -> list[dict]:
    """Questions on which the idea gives the wrong answer, with the correct answer (acted out in the sandbox)."""
    topic = rulebook.RULES[rid][0]
    bank = [q for q in rulebook.graded_bank(topic, 5) if q["question"] not in avoid]
    picks = act_out_batch({"SOUND": rulebook.SOUND_CODES[topic], rid: rulebook.RULES[rid][3]}, bank)
    apart = [{**q, "correct": picks["SOUND"][q["question"]], "idea_pick": picks[rid][q["question"]]} for q in bank
             if picks[rid][q["question"]] not in (picks["SOUND"][q["question"]], CANNOT_TELL)
             and not picks[rid][q["question"]].startswith("could not run")]
    apart.sort(key=lambda q: len(q["question"]))      # the simplest numbers first
    pool = apart[:20]                                  # simple, but enough of them that cases don't repeat
    return random.Random(seed).sample(pool, min(n, len(pool)))


def lesson(rid: str, trial: dict) -> dict:
    """The lesson after a proven idea: exact, short, and it can never restate the wrong idea as the rule."""
    from .practice import why
    topic = rulebook.RULES[rid][0]
    log = (trial.get("court_record") or {}).get("witness_log", [])
    followed = [w for w in log if w.get("answer") and w["answer"] != w.get("answer_if_sound")]
    if followed:
        w = followed[0]
        example = f"On '{w['question']}' you picked {w['answer']}. " + why(topic, w["question"], w["options"], w["answer_if_sound"])
    else:
        q = _counter_examples(rid, set(), 1, trial["trial_id"] + "-ex")[0]
        example = why(topic, q["question"], q["options"], q["correct"])
    asked = {w["question"] for w in log}
    t = _counter_examples(rid, asked, 1, f"{trial['trial_id']}-{trial.get('objections', 0)}-try")[0]
    return {"title": TITLES.get(topic, "Lesson"),
            # The verdict card already shows "You were thinking" and "Remember": the lesson is the worked example.
            "explanation": f"That idea works sometimes, but not always. {example}",
            "try_this": t["question"], "try_this_answer": t["correct"]}


def insight(trial: dict, decision: str, rid: str = "", lesson_shown: bool = True) -> dict:
    """What the court learned about the child's thinking, from their real answers (worked out exactly)."""
    from .practice import why
    log = (trial.get("court_record") or {}).get("witness_log", [])
    topic = rulebook.RULES[rid][0] if rid else (((trial.get("court_record") or {}).get("witness_plan") or {})
                                                .get("state", {}).get("topic", ""))
    if decision == "misconception_found" and rid:
        pts = [f"'{w['question']}': you picked {w['answer']}. " + why(topic, w["question"], w["options"], w["answer_if_sound"])
               for w in log if w.get("answer") and w["answer"] != w.get("answer_if_sound")][int(lesson_shown):3]
        # The verdict already names the idea and the lesson works through the first answer: say each thing once.
        head = "More answers that followed it:" if lesson_shown else "Your answers that followed it:"
        return {"headline": head if pts else "Now let's practise beating it!",
                "points": pts, "remember": REMEMBER[rid], "next": "practice"}
    if decision == "cleared":
        pts = [f"'{w['question']}': you picked {w['answer']}. That's right!" for w in log][:3]
        return {"headline": "Your thinking held up on every new question!", "points": pts,
                "remember": "Keep explaining your reasons. That's how you catch sneaky ideas.", "next": "checkup"}
    if log:
        return {"headline": "The court couldn't decide this time.",
                "points": ["Your answers did not all follow one idea, so the court won't guess."],
                "remember": ("Answer each question your own way. Next time, try it again with a few more questions."
                             if trial.get("source") == "checkup" else
                             "Try a check-up on this topic: a few quick questions show what you really think."),
                "next": "checkup"}
    return {}
