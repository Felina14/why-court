"""The court's voices: Amazon Polly reads every line aloud, in the child's language.

Each character has a voice (the Judge and the Prosecutor one, the Clerk and the Defence another). Polly has neural
voices for English (Indian English), Hindi, Spanish and French. It has none for Tamil or Swahili: for those the app
falls back to the browser's own voice, so a child still hears the court.
"""
from __future__ import annotations

import os
from functools import lru_cache

REGION = os.getenv("AWS_REGION", "us-east-1")

# language: {voice part: (VoiceId, engine, LanguageCode)}
VOICES = {
    "English": {"a": ("Kajal", "neural", "en-IN"), "b": ("Arjun", "generative", "en-IN")},
    "Hindi": {"a": ("Kajal", "neural", "hi-IN"), "b": ("Kajal", "neural", "hi-IN")},
    "Spanish": {"a": ("Lucia", "neural", "es-ES"), "b": ("Sergio", "neural", "es-ES")},
    "French": {"a": ("Lea", "neural", "fr-FR"), "b": ("Remi", "neural", "fr-FR")},
}
PART = {"judge": "b", "prosecutor": "b", "clerk": "a", "defence": "a", "narrator": "a"}


def available(lang: str) -> bool:
    return lang in VOICES


@lru_cache(maxsize=512)
def speak(text: str, lang: str = "English", speaker: str = "clerk") -> bytes | None:
    """MP3 of one court line, or None if Polly has no voice for this language (or is unavailable)."""
    text = (text or "").strip()[:1500]
    if not text or lang not in VOICES:
        return None
    voice, engine, code = VOICES[lang][PART.get(speaker, "a")]
    try:
        import boto3
        r = boto3.client("polly", region_name=REGION).synthesize_speech(
            Text=text, VoiceId=voice, Engine=engine, LanguageCode=code, OutputFormat="mp3")
        return r["AudioStream"].read()
    except Exception:
        return None
