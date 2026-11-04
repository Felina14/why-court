"""The court's Rule Book: wrong ideas children are known to hold, and the questions that tell them apart.

Asking a model to invent the exact rule inside a child's head from one sentence was the step that kept failing.
So for topics the Rule Book covers, the Prosecutor CHOOSES suspects from this book instead of inventing them, and
the surprise witnesses are picked by code: each next question is the one that best splits the ideas still in play.
The child's own answers eliminate ideas one by one. A wrong idea is only ever named when it is the last one standing
and the child followed it on at least two questions where it disagrees with correct understanding.

Every rule here is real code, run in the sandbox like any other rule. The ground truth is exact: arithmetic for
fractions and decimals, and for science and English a small bank of items whose facts are known (does it float, what
does it weigh; does the word start with a vowel SOUND). The entries come from well-known misconception research
("whole number thinking", "longer is larger", "gap thinking", "big things float", "an before a vowel letter").
Questions outside these topics still go to the Witness Builder agent.
"""
from __future__ import annotations

import random

import re
from fractions import Fraction
from itertools import combinations

from .sandbox import CANNOT_TELL, act_out_batch

SOUND = "SOUND"
MAX_WITNESSES = 6
EVIDENCE_NEEDED = 2  # questions where the idea and correct understanding disagree and the child followed the idea
SLIPS = 1            # a child who understands may slip once without being treated as holding a wrong idea.
# Wrong ideas get no such allowance: a different idea outside the book can look like "a book idea plus one slip",
# and naming the wrong idea is worse than naming none. (Tried and measured: allowing it mislabelled such a child.)

_WANTS_SMALLER = '"small" in question.lower() or "less" in question.lower()'


def _rule(key: str) -> str:
    return (f"def pick(question, options):\n"
            f"    key = {key}\n"
            f"    return min(options, key=key) if {_WANTS_SMALLER} else max(options, key=key)\n")


# id: (topic, the idea in plain words, how a child might say it, the idea acted out as code)
RULES: dict[str, tuple[str, str, str, str]] = {
    "top_number": ("fractions", "The bigger top number wins, whatever the bottom number is.",
                   "because 3 is bigger than 2", _rule("top")),
    "bottom_number": ("fractions", "The bigger bottom number wins, because there are more pieces.",
                      "because 8 is bigger than 5", _rule("bottom")),
    "smaller_bottom": ("fractions", "The smaller bottom number wins, because the pieces are bigger, "
                                    "whatever the top number is.",
                       "because thirds are bigger than sixths", _rule("lambda o: -bottom(o)")),
    "missing_pieces": ("fractions", "Fewer missing pieces (bottom minus top) wins; if that ties, more pieces wins.",
                       "because 4/5 is only missing 1 piece", _rule("lambda o: (top(o) - bottom(o), top(o))")),
    "whole_number_decimals": ("decimals", "The digits after the point are read as a whole number, so 0.45 beats "
                                          "0.5 because 45 is bigger than 5.",
                              "because 45 is bigger than 4", _rule("lambda o: int(digits_after_point(o) or 0)")),
    "shorter_is_larger": ("decimals", "Fewer digits after the point means bigger, because tenths are bigger than "
                                      "hundredths.",
                          "because tenths are bigger than hundredths",
                          _rule("lambda o: (-len(digits_after_point(o)), int(digits_after_point(o) or 0))")),
}
SOUND_CODE = _rule("num")

# ---------------- science: what floats? ----------------
# name: (size in cm, weight in grams, floats in water). Everyday objects whose answer is not in doubt.
FLOATING = {
    # Every name says its size, because the ideas being tested are about size and weight.
    "big wooden log": (200, 50000, True), "small stone": (3, 30, False), "tiny pebble": (1, 2, False),
    "big boulder": (150, 500000, False), "tiny wooden bead": (1, 0.5, True), "big beach ball": (60, 200, True),
    "small iron nail": (5, 5, False), "big block of ice": (50, 60000, True), "tiny coin": (2, 5, False),
    "big candle": (30, 400, True), "big brick": (20, 2500, False), "small cork": (3, 2, True),
    "big wooden door": (200, 30000, True), "small steel key": (5, 10, False), "small apple": (8, 150, True),
    "tiny glass marble": (2, 5, False), "light feather": (10, 0.1, True),
}


def _item(name: str) -> str:
    n = str(name).strip().lower().rstrip(".?!")
    for art in ("the ", "a ", "an "):
        if n.startswith(art):
            n = n[len(art):]
    return n


_FLOAT_CODE = (f"ITEMS = {FLOATING!r}\n"
               "def item(o):\n"
               "    n = str(o).strip().lower()\n"
               "    for art in ('the ', 'a ', 'an '):\n"
               "        if n.startswith(art):\n"
               "            n = n[len(art):]\n"
               "    return ITEMS[n]\n")


def _float_rule(body: str) -> str:
    return _FLOAT_CODE + "def pick(question, options):\n    " + body + "\n"


# ---------------- English: a or an? ----------------
# word: starts with a vowel SOUND (that is the real rule)
WORDS = {
    "apple": True, "egg": True, "umbrella": True, "elephant": True, "orange": True, "igloo": True, "owl": True,
    "ant": True, "hour": True, "honest": True, "ox": True, "island": True, "idea": True, "uncle": True,
    "university": False, "unicorn": False, "uniform": False, "one": False, "european": False, "banana": False,
    "dog": False, "house": False, "horse": False, "cat": False, "hospital": False, "helicopter": False,
    "caterpillar": False, "tree": False, "kite": False, "bag": False,
}
_WORD_CODE = (f"WORDS = {WORDS!r}\n"
              "def word(question):\n"
              "    return question.split('___')[1].strip().split()[0].strip('.?!,').lower()\n")


def _word_rule(body: str) -> str:
    return _WORD_CODE + "def pick(question, options):\n    w = word(question)\n    " + body + "\n"


def _an(cond: str) -> str:
    return f"return [o for o in options if o.lower() == ('an' if {cond} else 'a')][0]"


RULES.update({
    "big_floats": ("floating", "Big things float and small things sink, whatever they are made of.",
                   "because big things float", _float_rule("return max(options, key=lambda o: item(o)[0])")),
    "small_floats": ("floating", "Small things float and big things sink, whatever they are made of.",
                     "because it is small", _float_rule("return min(options, key=lambda o: item(o)[0])")),
    "light_floats": ("floating", "Light things float and heavy things sink, whatever they are made of.",
                     "because it is lighter", _float_rule("return min(options, key=lambda o: item(o)[1])")),
    "vowel_letter": ("a_an", "Use 'an' before any word that starts with the letter a, e, i, o or u, and 'a' "
                             "otherwise (looking at the letter, not the sound).",
                     "because umbrella starts with u", _word_rule(_an("w[0] in 'aeiou'"))),
    "long_word": ("a_an", "Long words take 'an' and short words take 'a'.",
                  "because umbrella is a long word", _word_rule(_an("len(w) >= 6"))),
})
# ---------------- negative numbers; multiplying and dividing ----------------
_INT = re.compile(r"^\s*-?\d+\s*$")
_OP = re.compile(r"^\s*\d+(\.\d+)?(\s*[×÷]\s*\d+(\.\d+)?)?\s*$")


def _value_rule(key: str) -> str:
    return (f"def pick(question, options):\n    key = {key}\n"
            f"    return min(options, key=key) if {_WANTS_SMALLER} else max(options, key=key)\n")


# ---------------- English: plurals and past tense ----------------
PLURALS = {"mouse": "mice", "child": "children", "foot": "feet", "tooth": "teeth", "man": "men", "woman": "women",
           "goose": "geese", "person": "people", "sheep": "sheep", "fish": "fish", "ox": "oxen", "leaf": "leaves",
           "knife": "knives", "wolf": "wolves"}
PAST = {"go": "went", "eat": "ate", "run": "ran", "see": "saw", "take": "took", "come": "came", "give": "gave",
        "write": "wrote", "sing": "sang", "drink": "drank", "swim": "swam", "catch": "caught", "think": "thought",
        "buy": "bought", "teach": "taught", "fly": "flew"}


def _form_code(table: str, words: dict, suffix: str) -> str:
    # The base word is whichever option is the base plus the suffix (the regular-looking form); the bank only holds
    # words whose real form is irregular, so that is where the rule and correct English disagree.
    return (f"{table} = {words!r}\n"
            "def base(options):\n"
            f"    for o in options:\n"
            f"        for b in {table}:\n"
            f"            if o.lower() in (b + {suffix!r}, b + {suffix[-1]!r}, b + b[-1] + {suffix!r}):\n"
            "                return b\n"
            f"    for o in options:\n"
            f"        for b, f in {table}.items():\n"
            "            if o.lower() == f:\n"
            "                return b\n")


def _form_rule(table: str, words: dict, suffix: str, body: str) -> str:
    return _form_code(table, words, suffix) + "def pick(question, options):\n    b = base(options)\n    " + body + "\n"


def _regular(suffix: str) -> str:
    return (f"return [o for o in options if o.lower() in (b + {suffix!r}, b + {suffix[-1]!r}, "
            f"b + b[-1] + {suffix!r})][0]")


RULES.update({
    "bigger_digits_negative": ("negatives", "With negative numbers, the one with the bigger digits is bigger, so -7 "
                                            "beats -3 because 7 is bigger than 3.",
                               "because 7 is bigger than 3", _value_rule("lambda o: abs(int(o))")),
    "multiply_bigger": ("multiply_divide", "Multiplying always makes a number bigger and dividing always makes it "
                                           "smaller, whatever you multiply or divide by.",
                        "because times makes it bigger",
                        _value_rule("lambda o: (1 if '×' in o else -1 if '÷' in o else 0)")),
    "add_s": ("plurals", "To make a plural, you always just add -s (one mouse, two mouses).",
              "because you add an s for more than one", _form_rule("PLURALS", PLURALS, "s", _regular("s"))),
    "add_ed": ("past_tense", "To talk about the past, you always just add -ed (I goed, I eated).",
               "because past things end in -ed", _form_rule("PAST", PAST, "ed", _regular("ed"))),
})

SOUND_CODES = {"fractions": SOUND_CODE, "decimals": SOUND_CODE,
               "floating": _float_rule("return [o for o in options if item(o)[2]][0]"),
               "a_an": _word_rule(_an("WORDS[w]")),
               "negatives": _value_rule("lambda o: int(o)"),
               "multiply_divide": _value_rule("lambda o: calculate(o)"),
               "plurals": _form_rule("PLURALS", PLURALS, "s", "return [o for o in options if o.lower() == PLURALS[b]][0]"),
               "past_tense": _form_rule("PAST", PAST, "ed", "return [o for o in options if o.lower() == PAST[b]][0]")}

_FRACTION = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
_DECIMAL = re.compile(r"^\s*\d*\.\d+\s*$")


def _blank_word(question: str) -> str:
    parts = str(question).split("___")
    if len(parts) < 2 or not parts[1].strip():
        return ""
    return parts[1].strip().split()[0].strip(".?!,").lower()


def topic_of(options: list[str], question: str = "") -> str:
    """The Rule Book topic this question belongs to, or '' if the book cannot test it."""
    if len(options) < 2:
        return ""
    if all(_FRACTION.match(o) for o in options):
        return "fractions"
    if all(_DECIMAL.match(o) for o in options):
        return "decimals"
    if "float" in question.lower() and len(options) == 2 and all(_item(o) in FLOATING for o in options) \
            and sum(FLOATING[_item(o)][2] for o in options) == 1:
        return "floating"
    if sorted(o.strip().lower() for o in options) == ["a", "an"] and _blank_word(question) in WORDS:
        return "a_an"
    if all(_INT.match(o) for o in options) and any(o.strip().startswith("-") for o in options):
        return "negatives"
    if all(_OP.match(o) for o in options) and any(("×" in o or "÷" in o) for o in options):
        return "multiply_divide"
    low = [o.strip().lower() for o in options]
    if "plural" in question.lower() and any(f in low for f in PLURALS.values()):
        return "plurals"
    if ("past" in question.lower() or "yesterday" in question.lower()) and any(f in low for f in PAST.values()):
        return "past_tense"
    return ""


def entries(topic: str) -> dict[str, str]:
    return {rid: idea for rid, (t, idea, _, _) in RULES.items() if t == topic}


def book_text(topic: str) -> str:
    return "\n".join(f'- {rid}: {idea} (a child might say: "{says}")'
                     for rid, (t, idea, says, _) in RULES.items() if t == topic)


def _bank(topic: str) -> list[dict]:
    """Every witness question the court may ask on this topic: simple pairs a 10-year-old can read."""
    if topic == "floating":
        art = lambda n: ("an " if n[0] in "aeiou" else "a ") + n
        # The size difference must be visible in the words: a child who thinks "big things float" cannot apply that
        # to "a tiny bead or a tiny coin" (measured: a simulated child fell back on "wood floats" there).
        size_word = lambda n: n.split()[0]
        visible = lambda x, y: size_word(x) != size_word(y) and max(FLOATING[x][0], FLOATING[y][0]) >= 3 * min(
            FLOATING[x][0], FLOATING[y][0])
        return [{"question": f"Which will float in water: {art(x)} or {art(y)}?", "options": [art(x), art(y)]}
                for x, y in combinations(FLOATING, 2) if FLOATING[x][2] != FLOATING[y][2] and visible(x, y)]
    if topic == "a_an":
        return [{"question": f"Fill in the blank with a or an: I saw ___ {w}.", "options": ["a", "an"]} for w in WORDS]
    if topic == "negatives":
        pairs = list(combinations(range(-9, 0), 2)) + [(p, -n) for p in range(1, 8) for n in range(p + 2, 10)]
        return [{"question": f"Which is bigger: {x} or {y}?", "options": [str(x), str(y)]} for x, y in pairs]   # two negatives: where "bigger digits" and the truth part
    if topic == "multiply_divide":
        out = []
        for n in range(2, 13):
            for f in ("0.5", "0.25", "0.1", "2", "3"):
                for op in ("×", "÷"):
                    out.append({"question": f"Which is bigger: {n} {op} {f} or {n}?", "options": [f"{n} {op} {f}", str(n)]})
        return out
    if topic == "plurals":
        return [{"question": f"What is the plural of {w}: {w}s or {p}?", "options": [f"{w}s", p]}
                for w, p in PLURALS.items() if p != f"{w}s"]
    if topic == "past_tense":
        reg = lambda w: w + ("d" if w.endswith("e") else "ed")
        return [{"question": f"Yesterday I ___ (past tense of {w}): {reg(w)} or {p}?", "options": [reg(w), p]}
                for w, p in PAST.items()]
    if topic == "fractions":
        vals = sorted({(a, b) for b in range(2, 11) for a in range(1, b)}, key=lambda x: (x[1], x[0]))
        nums = [f"{a}/{b}" for a, b in vals]
        pairs = [(x, y) for x, y in combinations(nums, 2) if Fraction(x) != Fraction(y)]
    else:
        nums = [f"0.{d}" for d in range(1, 10)] + [f"0.{d:02d}" for d in range(1, 100) if d % 10 and d % 3 == 0]
        pairs = [(x, y) for x, y in combinations(nums, 2) if Fraction(x) != Fraction(y)]
    return [{"question": f"Which is bigger: {x} or {y}?", "options": [x, y]} for x, y in pairs]


# Look-alikes: other wrong ideas children hold that are NOT in the Rule Book and are never charged. Before the court
# names a book idea, it asks one question where that idea and each look-alike disagree; if the child follows the book
# idea there too, the look-alike is ruled out. (Measured: a child who added top and bottom gave the same answers as
# "the bigger top number wins" on every question asked, and was mislabelled. On every question where "top number" is
# wrong, "add them up" is wrong the same way, so only a question where they disagree can tell them apart.)
SHADOWS = {
    "fractions": {"shadow:add_total": _rule("lambda o: top(o) + bottom(o)"),
                  "shadow:bigger_gap": _rule("lambda o: bottom(o) - top(o)")},
    "decimals": {"shadow:last_digit": _rule("lambda o: int(str(o).strip()[-1])")},
    "floating": {"shadow:wood_floats": _float_rule("return [o for o in options if 'wood' in o.lower()][0] "
                                                   "if any('wood' in o.lower() for o in options) else options[0]")},
    "a_an": {"shadow:always_an": _word_rule("return [o for o in options if o.lower() == 'an'][0]"),
             "shadow:vowel_or_h": _word_rule(_an("w[0] in 'aeiouh'"))},
    "multiply_divide": {"shadow:times_bigger_only": _value_rule("lambda o: 10**9 if '×' in o else calculate(o)")},
}


def _shadows(state: dict) -> list[str]:
    first = next(iter(state["table"].values()), {})
    return [h for h in first if h.startswith("shadow:")]


def unresolved_shadows(state: dict, idea: str) -> list[str]:
    """Look-alikes not yet ruled out for `idea` (ignoring any the question bank can never separate from it)."""
    out = []
    for sh in _shadows(state):
        separable = any(_usable(p, [idea, sh]) and p[idea] != p[sh] for p in state["table"].values())
        ruled_out = any(_usable(state["table"][q], [idea, sh]) and state["table"][q][idea] != state["table"][q][sh]
                        and a == state["table"][q][idea] for q, a in zip(state["asked"], state["answers"]))
        if separable and not ruled_out:
            out.append(sh)
    return out


def act_out_suspects(topic: str, suspects: list[str], case: dict) -> dict:
    """Run correct understanding and every idea in the book over the original question and the question bank.

    The ideas the Prosecutor chose are the suspects ("alive"). A suspect is dropped unless it reproduces the child's
    actual answer on the original question. The other ideas in the book are acted out too, but only so the court
    can double-check a child it is about to clear; they are never charged.
    """
    book = [rid for rid, r in RULES.items() if r[0] == topic]
    suspects = [s for s in dict.fromkeys(suspects) if s in book]
    original = {"question": case["question"].strip(), "options": list(case["options"])}
    bank = [q for q in _bank(topic) if q["question"].strip().lower() != original["question"].lower()
            and (_blank_word(q["question"]) != _blank_word(original["question"]) if topic == "a_an"
                 else {_item(o) for o in q["options"]} != {_item(o) for o in original["options"]})]
    rules = {SOUND: SOUND_CODES[topic], **{rid: RULES[rid][3] for rid in book}, **SHADOWS.get(topic, {})}
    picks = act_out_batch(rules, [original] + bank)
    on_original = {h: picks[h][original["question"]] for h in [SOUND] + suspects}
    dropped = {s: on_original[s] for s in suspects if on_original[s] != case["student_answer"]}
    alive = [SOUND] + [s for s in suspects if s not in dropped]
    table = {q["question"]: {h: picks[h][q["question"]] for h in rules} for q in bank}
    return {"topic": topic, "suspects": suspects, "alive": alive, "dropped": dropped, "on_original": on_original,
            "candidates": list(alive), "misses": {h: 0 for h in alive},
            "table": table, "options": {q["question"]: q["options"] for q in bank}, "asked": [], "answers": []}


TOPICS = {  # id: (name for the child, subject)
    "fractions": ("Comparing fractions", "maths"), "decimals": ("Comparing decimals", "maths"),
    "negatives": ("Negative numbers", "maths"), "multiply_divide": ("Multiplying and dividing", "maths"),
    "floating": ("What floats?", "science"), "a_an": ("'a' or 'an'", "english"),
    "plurals": ("Plurals", "english"), "past_tense": ("Past tense", "english"),
}


def graded_bank(topic: str, grade: int) -> list[dict]:
    """The question bank at the child's level: smaller numbers for younger children."""
    bank = _bank(topic)
    if topic == "fractions":
        top_bottom = 6 if grade <= 4 else 10
        bank = [q for q in bank if all(int(o.split("/")[1]) <= top_bottom for o in q["options"])]
    if topic == "multiply_divide" and grade <= 5:
        bank = [q for q in bank if any(f in q["question"] for f in ("× 0.5", "÷ 0.5", "× 2", "÷ 2"))]
    if topic == "decimals" and grade <= 4:
        bank = [q for q in bank if all(len(o.split(".")[1]) <= 2 for o in q["options"])]
    return bank


def open_state(topic: str, grade: int = 5) -> dict:
    """A check-up with no homework question: every idea in the book is a suspect, nothing is dropped up front."""
    book = [rid for rid, r in RULES.items() if r[0] == topic]
    bank = graded_bank(topic, grade)
    rules = {SOUND: SOUND_CODES[topic], **{rid: RULES[rid][3] for rid in book}, **SHADOWS.get(topic, {})}
    picks = act_out_batch(rules, bank)
    alive = [SOUND] + book
    return {"topic": topic, "grade": grade, "open": True, "suspects": book, "alive": alive, "dropped": {},
            "candidates": list(alive), "misses": {h: 0 for h in alive},
            "table": {q["question"]: {h: picks[h][q["question"]] for h in rules} for q in bank},
            "options": {q["question"]: q["options"] for q in bank}, "asked": [], "answers": []}


def slim(state: dict) -> dict:
    """The state without the question table (it is rebuilt exactly from the code, so it is never stored)."""
    return {k: v for k, v in state.items() if k not in ("table", "options")}


def restore(state: dict, case: dict) -> dict:
    if "table" not in state:
        full = open_state(state["topic"], state.get("grade", 5)) if state.get("open") else \
            act_out_suspects(state["topic"], state["suspects"], case)
        state = {**state, "table": full["table"], "options": full["options"]}
    return state


def _usable(picks: dict, who: list[str]) -> bool:
    return all(picks[h] != CANNOT_TELL and not picks[h].startswith("could not run") for h in who)


def next_question(state: dict) -> dict | None:
    """The question that best splits the ideas still alive, or None if the court has heard enough.

    Every question asked is one where at least one idea still in play disagrees with correct understanding, so each
    answer is real evidence. A child is cleared only after two answers that match correct understanding.
    """
    alive, asked = state["alive"], state["asked"]
    wrong = [h for h in alive if h != SOUND]
    if len(asked) >= MAX_WITNESSES or not alive:
        return None
    if not wrong:  # only correct understanding is left: confirm it once more against the rest of the book
        if SOUND not in alive or len(asked) >= 2:
            return None
        wrong = [h for h in state["table"][next(iter(state["table"]))] if h != SOUND]
        compare = wrong + [SOUND]
    else:
        if len(wrong) == 1 and SOUND not in alive and evidence_for(state, wrong[0]) >= EVIDENCE_NEEDED:
            return _confirming_question(state, wrong[0])
        compare = alive if SOUND in alive else alive + [SOUND]
    scored = []
    for q, picks in state["table"].items():
        if q in asked or not _usable(picks, compare):
            continue
        apart = sum(1 for h in wrong if picks[h] != picks[SOUND])
        if not apart:
            continue
        # Pairs of ideas still in play that this question tells apart: the more, the fewer questions the child needs.
        split = sum(1 for i, x in enumerate(alive) for y in alive[i + 1:] if picks[x] != picks[y])
        scored.append(((split, apart), len(q), q))
    if not scored:
        return None
    # Among the questions that split the ideas best, any short one will do: a seed per hearing picks among them, so
    # a child who objects, or does a check-up later, does not get the very same questions again.
    top = max(s[0] for s in scored)
    shortest = min(n for sc, n, _ in scored if sc == top)
    size = lambda q: sum(abs(int(x)) for x in re.findall(r"\d+", q))       # smaller numbers are easier to read
    ties = sorted((q for sc, n, q in scored if sc == top and n <= shortest + 2), key=lambda q: (size(q), q))[:10]   # ten simple ones: hearings vary
    best = random.Random(f"{state.get('seed', '')}-{len(asked)}").choice(ties) if state.get("seed") else ties[0]
    return {"question": best, "options": state["options"][best], "picks": state["table"][best]}


def _confirming_question(state: dict, idea: str) -> dict | None:
    """One more question, where `idea` and its unresolved look-alikes disagree; None if there is nothing to rule out."""
    left = unresolved_shadows(state, idea)
    if not left:
        return None
    best, best_score = None, None
    for q, picks in state["table"].items():
        if q in state["asked"] or not _usable(picks, [idea, *left]):
            continue
        apart = sum(1 for sh in left if picks[sh] != picks[idea])
        if apart and (best_score is None or (apart, -len(q)) > best_score):
            best, best_score = q, (apart, -len(q))
    if best is None:
        return None
    return {"question": best, "options": state["options"][best], "picks": state["table"][best]}


def evidence_for(state: dict, idea: str) -> int:
    """How many asked questions the child answered the way `idea` predicts AND unlike correct understanding."""
    return sum(1 for q, a in zip(state["asked"], state["answers"])
               if state["table"][q][idea] == a != state["table"][q][SOUND])


def hear_answer(state: dict, question: str, answer: str) -> None:
    """The child answered: an idea that predicted something else gets a miss and is ruled out. Correct understanding,
    and the idea the court charged from the child's own words, may slip once (measured: a simulated child misapplied
    its own rule once, and the charged idea was ruled out on that one answer)."""
    state["asked"].append(question)
    state["answers"].append(answer)
    misses = state.setdefault("misses", {h: 0 for h in state["alive"]})
    for h in state.get("candidates", state["alive"]):
        if state["table"][question][h] != answer:
            misses[h] = misses.get(h, 0) + 1
    state["alive"] = [h for h in state.get("candidates", state["alive"])
                      if misses.get(h, 0) <= (SLIPS if h == SOUND or h in state.get("charged", ()) else 0)]


def finding(state: dict) -> tuple[str, str]:
    """('misconception_found', idea_id) only with enough evidence; else ('cleared', '') or ('not_proven', '')."""
    alive = state["alive"]
    wrong = [h for h in alive if h != SOUND]
    if alive == [SOUND] and len(state["asked"]) >= 2 and not state.get("misses", {}).get(SOUND):
        return "cleared", ""
    if len(wrong) == 1 and SOUND not in alive and evidence_for(state, wrong[0]) >= EVIDENCE_NEEDED \
            and not unresolved_shadows(state, wrong[0]):
        return "misconception_found", wrong[0]
    return "not_proven", ""
