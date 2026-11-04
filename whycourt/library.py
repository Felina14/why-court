"""The Law Library: textbooks the court works from.

- Uploaded books (a school's or parent's own PDF) are indexed locally and never redistributed.
- The bundled starter book (books/starter_maths.json) is written by us, so it is free to ship.

Indexing: pypdf extracts page text; the Book Indexer agent reads the opening pages (table of contents) and
returns chapters with page ranges; exercises for a chapter are extracted lazily the first time it is opened.
"""
from __future__ import annotations

import io
import json
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from . import agents, blobs

BOOKS_DIR = Path(os.getenv("WHYCOURT_BOOKS", "data/books"))
BUNDLED_DIR = Path(__file__).resolve().parent.parent / "books"


class ChapterIndex(BaseModel):
    number: str = Field(description="Chapter number as printed, e.g. '7'")
    title: str
    start_page: int = Field(description="Printed or PDF page where the chapter starts")


class BookIndex(BaseModel):
    chapters: list[ChapterIndex]
    page_offset: int = Field(default=0, description="PDF page index minus printed page number, if printed numbers are used")


class Exercise(BaseModel):
    id: str = Field(description="Exercise label as printed, e.g. '7.2 Q3'")
    text: str = Field(description="The exercise exactly as printed")
    options: list[str] = Field(default_factory=list)
    answer: str = Field(default="", description="Correct answer if you are confident, else empty")


class ChapterExercises(BaseModel):
    key_rules: str = Field(description="The 2-4 key rules or ideas this chapter teaches, in the book's own words where possible")
    exercises: list[Exercise]


def _path(book_id: str) -> Path:
    p = BOOKS_DIR / f"{book_id}.json"
    return p if p.exists() else BUNDLED_DIR / f"{book_id}.json"


def list_books(class_code: str = "") -> list[dict]:
    """The built-in books, plus the books a teacher uploaded for this class (no one else sees those)."""
    books = list(blobs.all("books")) if blobs.on() else []
    for d in (BUNDLED_DIR, BOOKS_DIR):
        if d.exists():
            books += [json.loads(f.read_text()) for f in sorted(d.glob("*.json"))]
    return [{k: b.get(k) for k in ("book_id", "title", "subject", "grade", "origin", "attribution")} |
            {"chapters": len(b.get("chapters", []))}
            for b in books if b.get("origin") != "uploaded" or (class_code and b.get("class_code") == class_code)]


def get_book(book_id: str) -> Optional[dict]:
    if blobs.on() and re.fullmatch(r"[0-9a-f]{8}", book_id or "") and (b := blobs.get("books", book_id)):
        return b
    p = _path(book_id)
    return json.loads(p.read_text()) if p.exists() else None


def _save(book: dict) -> None:
    if blobs.on():
        return blobs.put("books", book["book_id"], book)
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    (BOOKS_DIR / f"{book['book_id']}.json").write_text(json.dumps(book, indent=1))


def add_pdf(pdf_bytes: bytes, title: str, subject: str, grade: str, class_code: str = "") -> dict:
    from pypdf import PdfReader

    pages = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages]
    toc_text = "\n\n".join(f"[PDF page {i + 1}]\n{t[:3000]}" for i, t in enumerate(pages[:12]))
    idx: BookIndex = agents.book_indexer()(
        f"Book: {title} ({subject}, grade {grade}). PDF has {len(pages)} pages.\n"
        f"Find the table of contents and list every chapter.\n\n{toc_text}",
        structured_output_model=BookIndex).structured_output

    chapters = sorted(idx.chapters, key=lambda c: c.start_page)
    out = []
    for i, c in enumerate(chapters):
        start = max(1, c.start_page + idx.page_offset)
        end = (chapters[i + 1].start_page + idx.page_offset - 1) if i + 1 < len(chapters) else len(pages)
        end = min(max(start, end), len(pages))
        out.append({"chapter_id": f"c{i + 1}", "number": c.number, "title": c.title,
                    "pages": [start, end], "text": "\n".join(pages[start - 1:end]), "key_rules": "", "exercises": None})
    book = {"book_id": uuid.uuid4().hex[:8], "title": title, "subject": subject, "grade": grade,
            "origin": "uploaded", "class_code": class_code, "chapters": out}
    _save(book)
    return {k: book[k] for k in ("book_id", "title", "subject", "grade")} | {"chapters": len(out)}


def chapter(book_id: str, chapter_id: str) -> Optional[dict]:
    """Return a chapter with its exercises, extracting them the first time."""
    book = get_book(book_id)
    if not book:
        return None
    ch = next((c for c in book["chapters"] if c["chapter_id"] == chapter_id), None)
    if not ch:
        return None
    if ch.get("exercises") is None:
        text = ch["text"]
        # Exercises usually sit after an 'Exercise' heading; send that part (or the chapter end) to the model.
        m = re.search(r"\bexercise", text, re.I)
        excerpt = text[m.start():][:14000] if m else text[-14000:]
        ex: ChapterExercises = agents.exercise_reader()(
            f"Chapter {ch['number']}: {ch['title']} ({book['subject']}, grade {book['grade']}).\n"
            f"Opening of the chapter:\n{text[:2500]}\n\nExercises section:\n{excerpt}",
            structured_output_model=ChapterExercises).structured_output
        ch["key_rules"] = ex.key_rules
        ch["exercises"] = [e.model_dump() for e in ex.exercises[:40]]
        if book.get("origin") == "uploaded":
            _save(book)
    return {k: v for k, v in ch.items() if k != "text"} | {"book_title": book["title"], "subject": book["subject"],
                                                            "grade": book["grade"], "attribution": book.get("attribution", "")}


def reference(book_id: str, chapter_id: str) -> str:
    """Short 'law book' excerpt the Judge and Defence can quote."""
    ch = chapter(book_id, chapter_id)
    if not ch:
        return ""
    return f"{ch['book_title']}, Chapter {ch['number']} '{ch['title']}'. Key rules: {ch['key_rules']}"
