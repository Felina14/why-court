"""Keeping children safe in Why Court. Three layers, none of them hard-coded rules about the child:

1. Amazon Bedrock Guardrails on every Nova call (set WHYCOURT_GUARDRAIL_ID / WHYCOURT_GUARDRAIL_VERSION;
   create one with scripts/create_guardrail.py). Filters harmful content and prompt attacks, and its
   denied topic stops any agent asking a child for personal details.
2. screen_child_text: before any agent sees what a child typed, the same guardrail screens it on its own
   (ApplyGuardrail) and removes names, phone numbers, emails and addresses.
3. The Kindness Officer: a small Nova agent reads every court line before it reaches the child and rewrites
   any line that shames, labels or scares. Set WHYCOURT_KINDNESS=off to skip it (e.g. in fast evals).
"""
from __future__ import annotations

import os
import re

GUARDRAIL_ID = os.getenv("WHYCOURT_GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.getenv("WHYCOURT_GUARDRAIL_VERSION", "DRAFT")
REGION = os.getenv("AWS_REGION", "us-east-1")
SAFE_LINE = "The court is taking a short break. Let's try that question another way!"


def model_guardrail_kwargs() -> dict:
    """Extra BedrockModel arguments that attach the guardrail to an agent's model (empty if not configured)."""
    if not GUARDRAIL_ID:
        return {}
    return {"guardrail_id": GUARDRAIL_ID, "guardrail_version": GUARDRAIL_VERSION,
            "guardrail_trace": "enabled", "guardrail_redact_input": True,
            "guardrail_redact_input_message": "[The court removed this message to keep you safe.]"}


def screen_child_text(text: str, source: str = "INPUT") -> tuple[str, bool]:
    """Return (safe_text, blocked). Personal details are replaced; harmful text is blocked.

    Without a configured guardrail the text passes through unchanged.
    """
    if not GUARDRAIL_ID or not text.strip():
        return text, False
    import boto3
    rt = boto3.client("bedrock-runtime", region_name=REGION)
    r = rt.apply_guardrail(guardrailIdentifier=GUARDRAIL_ID, guardrailVersion=GUARDRAIL_VERSION,
                           source=source, content=[{"text": {"text": text}}])
    if r.get("action") != "GUARDRAIL_INTERVENED":
        return text, False
    blocked = False
    for a in r.get("assessments") or []:
        items = ((a.get("contentPolicy") or {}).get("filters", []) + (a.get("topicPolicy") or {}).get("topics", [])
                 + (a.get("wordPolicy") or {}).get("customWords", []) + (a.get("wordPolicy") or {}).get("managedWordLists", []))
        blocked = blocked or any(i.get("action") == "BLOCKED" for i in items)
    out = "".join(o.get("text", "") for o in r.get("outputs") or []) or text
    return _keep_public_names(text, out, r), blocked


# Words that make a name in a child's text personal ("my friend Riya"), so it stays hidden.
_PERSONAL = re.compile(r"\b(my|me|mine|i am|i'm|im|our|we|friend|friends|teacher|mum|mom|mother|dad|father|"
                       r"brother|sister|cousin|aunt|uncle|grandma|grandpa|classmate|neighbour|neighbor|name is|"
                       r"called|lives|school)\b", re.I)


def _keep_public_names(original: str, masked: str, r: dict) -> str:
    """The guardrail hides every name. A name in a sentence with no personal context ("Archduke Franz Ferdinand was
    assassinated") is a public figure in schoolwork, not a child's private detail, so only then is it put back.
    Anything else the guardrail hid (emails, phones, addresses) always stays hidden."""
    if "{NAME}" not in masked or _PERSONAL.search(original):
        return masked
    other = [e for a in r.get("assessments") or [] for e in
             ((a.get("sensitiveInformationPolicy") or {}).get("piiEntities") or []) if e.get("type") != "NAME"]
    return masked if other else original


def kind_words(speaker: str, text: str) -> str:
    """Let the Kindness Officer agent approve or rewrite a court line before a child hears it."""
    if speaker == "student" or not text or os.getenv("WHYCOURT_KINDNESS", "on") == "off":
        return text
    try:
        from . import agents
        result = agents.kindness_officer()(  # fresh agent: no memory between lines
            f'The {speaker} is about to say to the child: "{text}"')
        if getattr(result, "stop_reason", "") == "guardrail_intervened":
            # The guardrail also anonymises harmless words it mistakes for names, so only a real BLOCK of the
            # line itself replaces it with the safe line.
            return SAFE_LINE if screen_child_text(text, source="OUTPUT")[1] else text
        import html
        first = next((html.unescape(ln).strip().strip('"') for ln in str(result).splitlines() if ln.strip()), "")
        return text if not first or first.upper().rstrip(".!") == "OK" else first
    except Exception:  # never let a safety check crash the trial; the Bedrock guardrail still applies
        return text
