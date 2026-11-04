"""Translate the app's own screen text (buttons, labels, hints) into each language, once, with checks.

  python scripts/translate_ui.py            # reads web/i18n/strings.json, writes web/i18n/<Language>.json

The court's lines are translated live by the Interpreter agent; this is only the fixed text of the app itself.
Done ahead of time so switching language is instant and every label can be reviewed. Each batch is sent with ids
and context; a result is redone on its own if a {n} placeholder or a symbol went missing, or if a short label came
back as a whole sentence (a model asked for one word sometimes writes a paragraph).
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from strands import Agent  # noqa: E402
from strands.models import BedrockModel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "web" / "i18n"
LANGS = ["Hindi", "Tamil", "Spanish", "French", "Swahili"]
MODEL = os.getenv("WHYCOURT_PRO_MODEL", "us.amazon.nova-pro-v1:0")
SYMBOLS = ["⚖", "→", "←", "✋", "➕", "📄", "…", "{n}"]

CONTEXT = """You translate the screen text of "Why Court", a game for children aged 8 to 14. A child gives an answer and
says why; a pretend courtroom (judge, prosecutor, defence, surprise witness) tests the reason. Use simple, warm,
everyday words a 10-year-old knows. Buttons stay short. A one-word label stays one word. Keep {n}, numbers, emoji
and symbols (⚖ → ← ✋ ➕ 📄 …) exactly. Courtroom words are part of the game: translate them as courtroom words.
Speak to the child informally, the same way every time (Hindi तुम, never आप; French tu; Spanish tú; Tamil நீ)."""


def _agent(lang: str) -> Agent:
    from whycourt.agents import _FORMS, GLOSSARY   # the same "you" and the same courtroom words as the live court
    return Agent(model=BedrockModel(model_id=MODEL, region_name=os.getenv("AWS_REGION", "us-east-1"), temperature=0.0),
                 system_prompt=CONTEXT + f"\nTarget language: {lang}." + _FORMS.get(lang, "") + GLOSSARY.get(lang, "")
                 + '\n"Why Court" is the name of the game: never translate it.', callback_handler=None)


# The polite "you" slips in (measured: about 25 Hindi labels used आप forms next to तुम ones on the same screen).
FORMAL = {"Hindi": r"आप|आइए|(?:दें|करें|लें|बताएं|बताएँ|दिखाएं|दिखाएँ|चुनें|सोचें|रखें|कहें|आज़माएं|आज़माएँ|छोड़ें|जोड़ें|बदलें|समझाएं|पढ़ें|देखें)(?![\u0900-\u097F])",
          "Tamil": r"உங்கள்|நீங்கள்|ுங்கள்",
          "French": r"\b(?:vous|votre|vos)\b|\b\w+ez\b(?<!\bchez)(?<!\bassez)",
          "Spanish": r"\busted(?:es)?\b"}


def _batch(lang: str, items: dict[str, str]) -> dict[str, str]:
    reply = str(_agent(lang)("Translate every value of this JSON object. Reply with ONLY the JSON object, same keys:\n"
                             + json.dumps(items, ensure_ascii=False, indent=0)))
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        out = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        out = {}
    return {k: str(v).strip() for k, v in out.items() if k in items and isinstance(v, str)}


def _one(lang: str, en: str) -> str:
    kind = "a single short label or button (keep it about as short as the English)" if len(en) < 25 else "one line"
    return str(_agent(lang)(f"Translate this {kind}. Reply with ONLY the translation:\n{en}")).strip().strip('"')


def _suspicious(en: str, tr: str, lang: str = "") -> str:
    if not tr:
        return "empty"
    if lang in FORMAL and re.search(FORMAL[lang], tr):
        return "formal 'you'"
    for sym in SYMBOLS:
        if en.count(sym) != tr.count(sym):
            return f"symbol {sym} changed"
    if len(en) <= 12 and len(tr) > 4 * len(en) + 10:
        return "short label became a sentence"
    if len(en) > 12 and len(tr) > 3.5 * len(en) + 20:
        return "much longer than the English"
    return ""


def translate(lang: str, strings: list[str]) -> dict[str, str]:
    done: dict[str, str] = {}
    if not strings:
        return done
    for i in range(0, len(strings), 30):
        chunk = strings[i:i + 30]
        got = _batch(lang, {f"s{j}": s for j, s in enumerate(chunk)})
        for j, en in enumerate(chunk):
            done[en] = got.get(f"s{j}", "")
    for en, tr in list(done.items()):
        why = _suspicious(en, tr, lang)
        if why:
            again = _one(lang, en)
            if _suspicious(en, again, lang) == "formal 'you'":
                again = _one(lang, en + "  (speak to ONE child, informally)")
            done[en] = again if not _suspicious(en, again, lang) else (tr if why == "formal 'you'" and tr else en)
            print(f"  {lang}: redid {en!r} ({why}) -> {done[en]!r}")
    return done


if __name__ == "__main__":
    strings = json.loads((ROOT / "strings.json").read_text())
    for lang in sys.argv[1:] or LANGS:
        path = ROOT / f"{lang}.json"
        have = json.loads(path.read_text()) if path.exists() else {}   # reviewed labels are kept; only new ones are sent
        if os.getenv("FRESH"):
            have = {}                                                   # FRESH=1: translate everything again
        out = {**have, **translate(lang, [x for x in strings if x not in have])}
        out = {k: out[k] for k in strings if k in out}
        (ROOT / f"{lang}.json").write_text(json.dumps(out, ensure_ascii=False, indent=0) + "\n")
        print(f"{lang}: {len(out)} strings, {sum(v == k for k, v in out.items())} left in English")
