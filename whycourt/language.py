"""The child's own language.

The court reasons in English (its Rule Book, its proofs), and the Interpreter, a small Nova agent, puts every line
the child sees into the child's language: the court characters, the witness questions, the verdict and the lesson.
Answer options are never translated: what the child taps is exactly what the court checks.
"""
from __future__ import annotations

import hashlib
import html
import re
from functools import lru_cache

LANGUAGES = ["English", "Hindi", "Tamil", "Spanish", "French", "Swahili"]
# A number, fraction or decimal, with its minus sign (but not a hyphen inside a word, as in "grade-5").
_NUM = re.compile(r"(?:(?<![\w])[-\u2212])?\d+(?:[./]\d+)?")


def normal(lang: str | None) -> str:
    lang = (lang or "English").strip().title()
    return lang if lang in LANGUAGES else "English"


@lru_cache(maxsize=2048)
def translate(text: str, lang: str) -> str:
    """Put one line into the child's language. English, or any failure, returns the line unchanged."""
    lang = normal(lang)
    if lang == "English" or not text or not text.strip():
        return text
    # Numbers are locked: a translator once "simplified" 15/20 into 3/4, which would teach a child a false fact.
    # Every number, fraction and decimal is swapped for a marker, then put back exactly. If any marker is lost,
    # the child gets the English line rather than a wrong one.
    from . import blobs
    key = hashlib.sha256(f"{lang}\n{text}".encode()).hexdigest()[:32] if blobs.on() else ""
    if key:   # shared by every Lambda copy: the court's fixed lines are translated once, not once per copy
        try:
            hit = blobs.get("translations", key)
            if hit:
                return hit["out"]
        except Exception:
            pass
    out = _translate(text, lang)
    if key and out != text:
        try:
            blobs.put("translations", key, {"lang": lang, "out": out})
        except Exception:
            pass
    return out


def _translate(text: str, lang: str) -> str:
    nums = _NUM.findall(text)
    masked = _NUM.sub(lambda m, c=iter(range(len(nums))): f"[[{next(c)}]]", text)
    try:
        from . import agents
        result = agents.interpreter(lang)(masked)
        if getattr(result, "stop_reason", "") == "guardrail_intervened":
            return text
        out = html.unescape(str(result)).strip().strip('"')   # models sometimes answer with &quot; and friends
        if not out or any(out.count(f"[[{i}]]") != 1 for i in range(len(nums))):
            return text
        if out.count("[[") != len(nums) or len(out) > 3 * len(text) + 40:
            return text   # an invented marker or a much longer line: the translator made something up
        for i, n in enumerate(nums):
            out = out.replace(f"[[{i}]]", n)
        return out
    except Exception:  # a missing translation must never break a trial
        return text

