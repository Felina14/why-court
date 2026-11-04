"""Why Court web API + mobile web app.

  uvicorn app.server:app --reload --port 8000   then open http://localhost:8000 (or your laptop's IP on a phone)
"""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from whycourt import checkup, classes, court, language, library, rehearing, rulebook, store, tracing, voice
from whycourt import practice as practice_round_lib
from whycourt.schemas import Case

tracing.setup()  # WHYCOURT_TRACE=console|otlp: every agent, tool and Graph node as an OpenTelemetry span
app = FastAPI(title="Why Court")
WEB = Path(__file__).resolve().parent.parent / "web"


class TrialIn(BaseModel):
    case: Case
    player: str = "guest"
    lang: str = "English"
    class_code: str = ""
    live: str = ""          # a random key the waiting browser polls for the court's progress


class CheckupIn(BaseModel):
    topic: str = ""
    book_id: str = ""
    chapter_id: str = ""
    grade: int = 5
    player: str = "guest"
    class_code: str = ""
    lang: str = "English"


class CheckupAnswerIn(BaseModel):
    answer: str
    why: str = ""


class ClassIn(BaseModel):
    name: str
    pin: str


class AnswerIn(BaseModel):
    answer: str


class SpeakIn(BaseModel):
    text: str
    lang: str = "English"
    speaker: str = "clerk"


class RehearIn(BaseModel):
    answers: list[str]


class ObjectIn(BaseModel):
    new_why: str
    live: str = ""


# ---------------- limits: every endpoint that spends money on AWS is rate-limited per visitor ----------------

_HITS: dict[tuple[str, str], list[float]] = {}   # one process; on Lambda this would live in DynamoDB


def limit(name: str, per_minute: int):
    def check(request: Request) -> None:
        import time
        key = (name, request.client.host if request.client else "?")
        now = time.time()
        hits = [t for t in _HITS.get(key, []) if now - t < 60]
        if len(hits) >= per_minute:
            raise HTTPException(429, "The court needs a short break. Try again in a minute.")
        _HITS[key] = hits + [now]
    return Depends(check)


MAX_PHOTO, MAX_PDF = 10 * 2**20, 40 * 2**20

# One answer at a time per trial: a double tap must not resume the same paused Graph twice.
_TRIAL_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()


@contextmanager
def one_at_a_time(trial_id: str):
    with _LOCKS_LOCK:
        lock = _TRIAL_LOCKS.setdefault(trial_id, threading.Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "The court is already hearing that answer.")
    try:
        yield
    finally:
        lock.release()


def _must(trial_id: str) -> dict:
    t = store.get(trial_id)
    if not t:
        raise HTTPException(404, "No such trial")
    return t


@app.post("/api/homework", dependencies=[limit("homework", 10)])
async def homework(photo: Optional[UploadFile] = File(None), text: str = Form("")):
    """Upload a homework photo (or typed homework). Returns the answered questions, ready for trial."""
    if not photo and not text.strip():
        raise HTTPException(400, "Send a photo or some text")
    data, fmt = None, "jpeg"
    if photo:
        data = await photo.read(MAX_PHOTO + 1)
        if len(data) > MAX_PHOTO:
            raise HTTPException(413, "That photo is too big (10 MB at most)")
        ct = (photo.content_type or "").lower()
        fmt = "png" if "png" in ct else "webp" if "webp" in ct else "jpeg"
    if len(text) > 20000:
        raise HTTPException(413, "That is a lot of homework! Send one page at a time.")
    # Reading takes a Nova call: run it off the event loop so other children are not kept waiting.
    cases, notes = await run_in_threadpool(court.read_homework, data, fmt, text)
    return {"cases": [c.model_dump() for c in cases], "unreadable": notes}


_LIVE_KEY = re.compile(r"[0-9a-f]{16,32}")


def _live(key: str):
    """The court's progress, as fixed lines, for the browser that is waiting (GET /api/live/{key})."""
    return court.live_feed(lambda lines: store.save_live(key, lines)) if _LIVE_KEY.fullmatch(key or "") else None


@app.get("/api/live/{key}")
def live(key: str):
    if not _LIVE_KEY.fullmatch(key):
        raise HTTPException(404, "No such hearing")
    return {"lines": store.get_live(key)}


@app.post("/api/trial", dependencies=[limit("trial", 6)])
def start_trial(t: TrialIn):
    # Case history: the wrong ideas this player was shown to hold before (newest first, at most 3).
    seen = [x["misconception"] for x in reversed(store.player_trials(t.player))
            if x["status"] == "misconception_found" and x.get("misconception")]
    case = t.case.model_copy(update={"history": list(dict.fromkeys(seen))[:3]}) if t.player != "guest" else t.case
    trial = court.new_trial(case, t.lang)
    trial["player"] = t.player
    trial["class_code"] = classes.normal_code(t.class_code) if classes.get(t.class_code) else ""
    court.hold_trial(trial, live=_live(t.live))
    store.save(trial)
    return court.public_view(trial)


@app.post("/api/trial/{trial_id}/witness")
def witness(trial_id: str, a: AnswerIn):
    with one_at_a_time(trial_id):
        trial = _must(trial_id)
        if trial["status"] != "awaiting_witness":
            raise HTTPException(409, "No witness waiting")
        court.answer_witness(trial, a.answer)
        rehearing.schedule(trial)          # a proven Rule Book idea gets a re-hearing: did the lesson work?
        store.save(trial)
        return court.public_view(trial)


@app.get("/api/trial/{trial_id}/practice")
def practice_round(trial_id: str):
    """Guided practice right after a wrong idea was found: questions where the old idea gives the wrong answer."""
    trial = _must(trial_id)
    out = practice_round_lib.start(trial)
    if not out:
        raise HTTPException(404, "No practice round for this trial")
    store.save(trial)
    return out


@app.post("/api/trial/{trial_id}/practice/more", dependencies=[limit("more", 10)])
def practice_more(trial_id: str):
    """Two more tries after a hard practice round (or when a re-hearing finds the idea still there)."""
    with one_at_a_time(trial_id):
        trial = _must(trial_id)
        try:
            out = practice_round_lib.more(trial)
        except KeyError:
            raise HTTPException(404, "No practice round for this trial")
        store.save(trial)
        return out


@app.post("/api/trial/{trial_id}/practice/{i}")
def practice_answer(trial_id: str, i: int, a: AnswerIn):
    with one_at_a_time(trial_id):
        trial = _must(trial_id)
        if not trial.get("practice"):
            practice_round_lib.start(trial)
        try:
            out = practice_round_lib.answer(trial, i, a.answer)
        except KeyError:
            raise HTTPException(404, "No such practice question")
        store.save(trial)
        return out


@app.post("/api/trial/{trial_id}/teach", dependencies=[limit("teach", 6)])
def teach_me(trial_id: str):
    """'Teach me' after a wrong answer."""
    with one_at_a_time(trial_id):
        trial = _must(trial_id)
        if trial["status"] != "help":
            raise HTTPException(409, "Teach me is for an answer that is not right yet")
        out = court.teach(trial)
        if not out:
            raise HTTPException(503, "The court couldn't write that lesson right now. Try again!")
        store.save(trial)
        return out


@app.post("/api/trial/{trial_id}/object", dependencies=[limit("object", 6)])
def objection(trial_id: str, o: ObjectIn):
    with one_at_a_time(trial_id):
        trial = _must(trial_id)
        court.object_(trial, o.new_why, live=_live(o.live))
        store.save(trial)
        return court.public_view(trial)


# ---------------- chapter check-up ----------------

@app.get("/api/topics")
def topics():
    return [{"id": t, "name": name, "subject": subj} for t, (name, subj) in rulebook.TOPICS.items()]


@app.post("/api/checkup", dependencies=[limit("checkup", 10)])
def start_checkup(c: CheckupIn):
    """Questions at the child's level that reveal a sneaky idea before it costs marks."""
    topic = c.topic or (checkup.topic_for_chapter(c.book_id, c.chapter_id) if c.book_id and c.chapter_id else "")
    if not topic:
        raise HTTPException(422, "The court has no check-up for this chapter yet. Pick a topic instead.")
    try:
        trial = checkup.start(topic, c.grade, c.player, classes.normal_code(c.class_code) if classes.get(c.class_code) else "", c.lang)
    except ValueError as e:
        raise HTTPException(422, str(e))
    q = checkup.question(trial)
    store.save(trial)
    return {"trial_id": trial["trial_id"], "topic": topic, "question": q, "n": 1,
            "topic_name": language.translate(trial["checkup"]["name"], trial["lang"])}


@app.post("/api/checkup/{trial_id}")
def answer_checkup(trial_id: str, a: CheckupAnswerIn):
    with one_at_a_time(trial_id):
        trial = _must(trial_id)
        if trial.get("source") != "checkup" or trial["status"] != "checkup":
            raise HTTPException(409, "This check-up is finished")
        out = checkup.answer(trial, a.answer, a.why)
        if out.get("done"):
            rehearing.schedule(trial)        # a found idea comes back on re-hearing day, like a trial's
        store.save(trial)
        return out


# ---------------- classes and the teacher desk ----------------

@app.post("/api/classes", dependencies=[limit("classes", 5)])
def new_class(c: ClassIn):
    """A teacher starts a class: name + PIN in, a class code out (to give the pupils)."""
    try:
        return classes.create(c.name, c.pin)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/classes/{code}")
def class_info(code: str):
    c = classes.get(code)
    if not c:
        raise HTTPException(404, "No such class")
    return c


_MAX_FAILS, _WINDOW = 5, 600


def _class_trials(class_: str, pin: str) -> list[dict]:
    """Only this class's trials, only with the right PIN, and only 5 wrong PINs per class per 10 minutes.
    The count is shared by every server copy (S3 on Lambda), so guesses cannot be spread across copies."""
    import time
    code = classes.normal_code(class_)
    now = time.time()
    recent = [t for t in store.pin_fails(code) if now - t < _WINDOW]
    if len(recent) >= _MAX_FAILS:
        raise HTTPException(429, "Too many wrong PINs for this class. Wait 10 minutes.")
    if not classes.check(code, pin):
        if code:
            store.set_pin_fails(code, recent + [now])
        raise HTTPException(401, "Wrong class code or PIN")
    if recent:
        store.set_pin_fails(code, [])
    return store.class_trials(code)


# The class code and PIN travel in headers, never in the address: addresses end up in logs and browser history.
ClassCode = Header("", alias="X-Class-Code")
ClassPin = Header("", alias="X-Class-Pin")


@app.get("/api/teacher")
def teacher(class_: str = ClassCode, pin: str = ClassPin):
    trials = _class_trials(class_, pin)
    found = [t for t in trials if t["status"] == "misconception_found"]
    return {"total_trials": len(trials), "confirmed": found,
            "closed": sum(t["status"] == "cleared" or t.get("verdict_kind") == "held_up" for t in trials),
            "recent": [_case_file(t) for t in trials[-15:][::-1]],
            "rehearings": rehearing.summary(trials), "class": classes.get(class_)}


@app.post("/api/speak", dependencies=[limit("speak", 60)])
def speak(s: SpeakIn):
    """Amazon Polly reads one court line in the child's language. 204 = no Polly voice: the browser speaks instead."""
    audio = voice.speak(s.text, language.normal(s.lang), s.speaker)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/rehearings")
def rehearings(player: str = "guest"):
    """Re-hearings this player can take now (a proven wrong idea, re-tested days later)."""
    return {"due": rehearing.due(player)}


@app.post("/api/rehearings/{rid}")
def answer_rehearing(rid: str, a: RehearIn):
    try:
        return rehearing.answer(rid, a.answers)
    except KeyError:
        raise HTTPException(404, "No such re-hearing, or it is already done")


def _rehearing_of(t: dict) -> dict | None:
    r = store.get_rehearing(t["rehearing_id"]) if t.get("rehearing_id") else None
    if not r:
        return None
    return {"done": r["done"], "result": r.get("result"), "due_at": r["due_at"],
            "right": sum(a == q["correct"] for a, q in zip(r.get("answers") or [], r["questions"])), "of": len(r["questions"])}


def _case_file(t: dict) -> dict:
    """What the teacher sees of one trial: how the Strands Graph ran, who said what, and what the answers proved."""
    rec = t.get("court_record") or {}
    return {"trial_id": t["trial_id"], "player": t.get("player", ""), "status": t["status"],
            "question": t["case"]["question"], "answer": t["case"].get("student_answer", "") or ", ".join(t.get("witness_answers") or []),
            "why": t["case"]["student_why"] or " / ".join(w for w in t.get("checkup_whys", []) if w),
            "when": t.get("created_at"), "misconception": t.get("misconception"),
            "rehearing": _rehearing_of(t),
            "timeline": rec.get("timeline", []),
            "rulings": {k: {x: rec[k].get(x) for x in ("decision", "wrong_idea", "suspects")}
                        for k in ("usher", "clerk", "prosecutor", "defence", "judge", "examiner") if k in rec},
            "witnesses": rec.get("witness_log", []), "overruled": rec.get("overruled", []),
            "tools": [{"agent": x["agent"], "tool": x["tool"]} for x in rec.get("stenographer", [])],
            "reteach": rec.get("reteach"), "error": t.get("error", ""),
            "practice": ({"score": sum(a["correct"] for a in t["practice"]["answers"]),
                          "answered": len(t["practice"]["answers"]), "of": len(t["practice"]["questions"])}
                         if t.get("practice") else None)}


@app.post("/api/teacher/summary", dependencies=[limit("summary", 5)])
def teacher_summary(class_: str = ClassCode, pin: str = ClassPin):
    return {"summary": court.teacher_summary(_class_trials(class_, pin))}


@app.post("/api/teacher/approve/{trial_id}")
def approve(trial_id: str, class_: str = ClassCode, pin: str = ClassPin):
    if trial_id not in {t["trial_id"] for t in _class_trials(class_, pin)}:
        raise HTTPException(404, "No such trial in this class")
    trial = _must(trial_id)
    trial["teacher_approved"] = True
    store.save(trial)
    return {"ok": True}



# ---------------- Law Library (textbooks) ----------------

@app.get("/api/books")
def books(class_: str = ""):
    """Built-in books, and the textbooks this child's class has added (?class_=CODE)."""
    return library.list_books(classes.normal_code(class_))


@app.post("/api/books", dependencies=[limit("books", 2)])
async def add_book(pdf: UploadFile = File(...), title: str = Form(...), subject: str = Form("maths"), grade: str = Form(""),
                   class_: str = ClassCode, pin: str = ClassPin):
    """A teacher adds their class's textbook PDF (class code + PIN). Only that class sees it; never redistributed."""
    _class_trials(class_, pin)               # the same PIN check (and wrong-PIN lockout) as the teacher desk
    data = await pdf.read(MAX_PDF + 1)
    if len(data) > MAX_PDF:
        raise HTTPException(413, "That book is too big (40 MB at most)")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "That file isn't a PDF. Choose the PDF of your textbook.")
    if not title.strip():
        raise HTTPException(400, "Give the book a title.")
    return await run_in_threadpool(library.add_pdf, data, title.strip()[:120], subject[:40], grade[:20],
                                   classes.normal_code(class_))


@app.get("/api/books/{book_id}")
def book(book_id: str):
    b = library.get_book(book_id)
    if not b:
        raise HTTPException(404, "No such book")
    return {k: b[k] for k in ("book_id", "title", "subject", "grade")} | {
        "chapters": [{"chapter_id": c["chapter_id"], "number": c["number"], "title": c["title"]} for c in b["chapters"]]}


@app.get("/api/books/{book_id}/chapters/{chapter_id}")
def chapter(book_id: str, chapter_id: str):
    ch = library.chapter(book_id, chapter_id)
    if not ch:
        raise HTTPException(404, "No such chapter")
    return ch

try:   # on AWS Lambda (behind a function URL) the same app runs through Mangum
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None

app.mount("/static", StaticFiles(directory=WEB), name="static")


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
           '<text y=".9em" font-size="90">⚖️</text></svg>')


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(FAVICON, media_type="image/svg+xml")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/teacher")
def teacher_page():
    return FileResponse(WEB / "teacher.html")
