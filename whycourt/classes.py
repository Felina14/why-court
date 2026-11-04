"""Classes: a teacher sees only their own pupils, and no child ever needs an account.

A teacher starts a class with a name and a PIN and gets a short class code (like 5B-K7Q2) to give the pupils. A child
types the class code once; their trials then belong to that class. The teacher desk opens only with the class code
and the PIN. The PIN is stored salted and hashed. No names, no emails, no passwords for children.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from pathlib import Path

_PATH = Path(os.getenv("WHYCOURT_CLASSES", str(Path(os.getenv("WHYCOURT_DATA", "data/trials.json")).parent / "classes.json")))
_LOCK = threading.Lock()
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I/L: easy to copy off a whiteboard


def _load() -> dict:
    from . import blobs
    if blobs.on():
        return {c["code"]: c for c in blobs.all("classes")}
    return json.loads(_PATH.read_text()) if _PATH.exists() else {}


def _hash(pin: str, salt: str) -> str:
    return hashlib.sha256((salt + ":" + pin).encode()).hexdigest()


def normal_code(code: str | None) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(code or "").upper())[:12]


def create(name: str, pin: str) -> dict:
    name = str(name).strip()[:40]
    if not name or not re.fullmatch(r"\d{4,8}", str(pin)):
        raise ValueError("A class needs a name and a PIN of 4 to 8 digits")
    prefix = re.sub(r"[^A-Z0-9]", "", re.sub(r"<[^>]*>", "", name).upper())[:3] or "CLS"
    with _LOCK:
        db = _load()
        while True:
            code = f"{prefix}-{''.join(secrets.choice(_ALPHABET) for _ in range(4))}"
            if code not in db:
                break
        salt = secrets.token_hex(8)
        db[code] = {"code": code, "name": name, "salt": salt, "pin": _hash(str(pin), salt)}
        from . import blobs
        if blobs.on():
            blobs.put("classes", code, db[code])
        else:
            from .store import _atomic_write
            _atomic_write(_PATH, db)
    return {"code": code, "name": name}


def get(code: str) -> dict | None:
    c = _load().get(normal_code(code))
    return {"code": c["code"], "name": c["name"]} if c else None


def check(code: str, pin: str) -> bool:
    c = _load().get(normal_code(code))
    return bool(c) and secrets.compare_digest(c["pin"], _hash(str(pin), c["salt"]))
