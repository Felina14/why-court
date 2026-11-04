"""Tiny JSON-file store for trials. Swap for DynamoDB / AgentCore Memory on deploy.
Stores no names: only an anonymous player code."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from . import blobs

_PATH = Path(os.getenv("WHYCOURT_DATA", "data/trials.json"))
_LOCK = threading.RLock()


def _atomic_write(path: Path, data) -> None:
    """Write a whole file so that a reader sees either the old version or the new one, never half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.replace(tmp, path)


def _load() -> dict:
    with _LOCK:
        return json.loads(_PATH.read_text()) if _PATH.exists() else {}


def _safe(key: str) -> str:
    return "".join(c for c in str(key) if c.isalnum() or c in "-_")[:40]


def save(trial: dict) -> None:
    trial.setdefault("created_at", time.time())   # keeps the teacher's "recent" list in order on S3
    if blobs.on():
        blobs.put("trials", trial["trial_id"], trial)
        # Indexes, so a child's history and a class's desk read only their own trials (never every trial stored).
        if trial.get("class_code"):
            blobs.mark(f"byclass/{_safe(trial['class_code'])}", trial["trial_id"])
        if trial.get("player", "guest") != "guest":
            blobs.mark(f"byplayer/{_safe(trial['player'])}", trial["trial_id"])
        return
    with _LOCK:
        db = json.loads(_PATH.read_text()) if _PATH.exists() else {}
        db[trial["trial_id"]] = trial
        _atomic_write(_PATH, db)


def get(trial_id: str) -> dict | None:
    if blobs.on():
        return blobs.get("trials", trial_id)
    return _load().get(trial_id)


def _by_time(ts: list[dict]) -> list[dict]:
    return sorted(ts, key=lambda t: t.get("created_at") or 0)


def class_trials(code: str) -> list[dict]:
    if not code:
        return []
    if blobs.on():
        return _by_time(blobs.get_many("trials", blobs.marked(f"byclass/{_safe(code)}")))
    return [t for t in all_trials() if t.get("class_code") == code]


def player_trials(player: str) -> list[dict]:
    if not player or player == "guest":
        return []
    if blobs.on():
        return _by_time(blobs.get_many("trials", blobs.marked(f"byplayer/{_safe(player)}")))
    return [t for t in all_trials() if t.get("player") == player]


def all_trials() -> list[dict]:
    if blobs.on():
        return sorted(blobs.all("trials"), key=lambda t: t.get("created_at") or 0)
    return list(_load().values())


# ---------------- re-hearings (a separate file, same simple store) ----------------

_RPATH = Path(os.getenv("WHYCOURT_REHEARINGS", str(_PATH.parent / "rehearings.json")))


def _rload() -> dict:
    with _LOCK:
        return json.loads(_RPATH.read_text()) if _RPATH.exists() else {}


def save_rehearing(r: dict) -> None:
    if blobs.on():
        blobs.put("rehearings", r["id"], r)
        blobs.mark(f"rhplayer/{_safe(r.get('player', 'guest'))}", r["id"])
        return
    with _LOCK:
        db = json.loads(_RPATH.read_text()) if _RPATH.exists() else {}
        db[r["id"]] = r
        _atomic_write(_RPATH, db)


def get_rehearing(rid: str) -> dict | None:
    if blobs.on():
        return blobs.get("rehearings", rid)
    return _rload().get(rid)


def player_rehearings(player: str) -> list[dict]:
    if blobs.on():
        return blobs.get_many("rehearings", blobs.marked(f"rhplayer/{_safe(player)}"))
    return [r for r in all_rehearings() if r["player"] == player]


def rehearings_of(trials: list[dict]) -> list[dict]:
    """The re-hearings booked for these trials (one class's desk)."""
    ids = [t["rehearing_id"] for t in trials if t.get("rehearing_id")]
    if blobs.on():
        return blobs.get_many("rehearings", ids)
    wanted = set(ids)
    return [r for r in all_rehearings() if r["id"] in wanted]


def all_rehearings() -> list[dict]:
    if blobs.on():
        return blobs.all("rehearings")
    return list(_rload().values())


# ---------------- the live feed: what the court is doing while a child waits ----------------
# One process locally (a dict); on Lambda the waiting browser's poll lands on another instance, so it goes to S3.

_LIVE: dict[str, list] = {}


def save_live(key: str, lines: list[dict]) -> None:
    _LIVE[key] = lines
    if blobs.on():
        blobs.put("live", key, {"lines": lines})


def get_live(key: str) -> list[dict]:
    if key in _LIVE:
        return _LIVE[key]
    return (blobs.get("live", key) or {}).get("lines", []) if blobs.on() else []


# ---------------- wrong teacher PINs, per class (shared by every Lambda copy, or one process locally) ----------------

_FAILS: dict[str, list] = {}


def pin_fails(code: str) -> list[float]:
    if blobs.on():
        return (blobs.get("pinfails", code) or {}).get("times", [])
    return _FAILS.get(code, [])


def set_pin_fails(code: str, times: list[float]) -> None:
    if blobs.on():
        blobs.put("pinfails", code, {"times": times})
    else:
        _FAILS[code] = times
