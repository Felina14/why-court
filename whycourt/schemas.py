"""Typed records every courtroom agent returns (Strands structured output). Works for any subject."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

class Case(BaseModel):
    """One answered question brought to court: from homework, practice, or a story episode."""
    case_id: str = ""
    subject: str = "maths"
    grade: Optional[str] = None
    question: str
    options: list[str] = Field(default_factory=list)
    student_answer: str
    student_why: str = ""
    correct_answer: Optional[str] = None
    source: Literal["homework", "practice", "episode", "book"] = "practice"
    book_ref: str = Field(default="", description="Textbook chapter this case comes from, quoted by the court")
    book_id: str = Field(default="", description="Law Library book this case came from, if any")
    chapter_id: str = Field(default="", description="Chapter within that book, so the court can borrow its other exercises")
    history: list[str] = Field(default_factory=list,
                               description="Wrong ideas this child was shown to hold in earlier trials (case history)")


# ---------- intake ----------

class HomeworkItem(BaseModel):
    question: str = Field(description="The question exactly as written")
    options: list[str] = Field(default_factory=list, description="The answer choices. For 'Which is bigger: A or B?' "
                               "they are A and B. Empty only if the question offers no choices")
    student_answer: str = Field(description="ONLY the answer itself, e.g. '3/5' or 'an' - never the reason")
    student_reason: str = Field(default="", description="The child's own words explaining HOW they knew, copied "
                               "exactly: everything after 'because', any working, any note in the margin. "
                               "Empty ONLY if they truly wrote no reason at all.")
    subject: str = Field(description="maths, science, english, social science, or other")


class HomeworkPage(BaseModel):
    items: list[HomeworkItem]
    unreadable_notes: str = Field(default="", description="Anything that could not be read clearly")


class CourtLines(BaseModel):
    """What the court characters say aloud to the child before the verdict. No analysis, no spoilers."""
    prosecutor: str = Field(default="", description="One short in-character line")
    defence: str = Field(default="", description="One short in-character line")
    judge: str = Field(default="", description="One short in-character line")


class ReasonFeedback(BaseModel):
    """Feedback on a child's reason, for an 8-14 year old: honest, kind, specific."""
    good: str = Field(description="One specific thing the child did well in their reason (one short sentence)")
    think: str = Field(description="One thing to think about: a gap, a missing step, or a stronger way to say it. "
                                   "If the reason is fully sound, a next-level idea to explore")
    try_this: str = Field(description="One short question that pushes the same reasoning a step further")
