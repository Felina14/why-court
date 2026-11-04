"""Why Court, run by agents. The whole trial is ONE Strands Graph run that pauses for the child.

  usher (outside the Graph: is there a reason at all?)
  clerk ──trial──► hearing ──► judge ──cross_examine──► [witness_builder] ──► examiner ──misconception_found──► tutor
                   (Swarm:                                (only for topics      (Judge at the witness  (writes the lesson,
                    prosecutor ⇄ defence)                  outside the           stand: call_witness    asks the Maths
                                                           Rule Book)            raises an INTERRUPT)   Expert agent as a tool)

- Graph: the court's fixed procedure. Edges only read rulings the agents filed with record_ruling.
- Swarm: the hearing is a real debate; the Prosecutor hands the floor to the Defence.
- Interrupts: each surprise witness pauses the Graph inside the call_witness tool. The child answers on their own
  screen, and the Graph resumes exactly where it stopped. One trial, one Graph, however many witnesses.
- Hooks: CourtRules on every agent (proof before verdict, no early verdict, charges get tested, checked lessons,
  kindness, stenographer); CourtOfficers on the Graph run the Usher (before the Clerk) and the Narrator (after the
  Judge) with a deliberately narrow view; Timekeeper records the order and timing of the nodes.
- Agents as tools: the Verifier audits the Witness Builder; the Maths Expert checks the Tutor's lesson.
- Session manager: a paused trial is saved (S3SessionManager when WHYCOURT_SESSION_BUCKET is set, else
  FileSessionManager), one session per trial, so the child can answer on their own time, even after a restart.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional

from strands.multiagent import GraphBuilder, Swarm
from strands.multiagent.base import Status
from strands.session.file_session_manager import FileSessionManager


from . import agents, lessons, rulebook, witness
from .guardrails import kind_words, screen_child_text
from .language import normal as language, translate
from .hooks import CourtOfficers, Timekeeper
from .schemas import Case, CourtLines, HomeworkPage

ROLES = {"clerk": "clerk", "prosecutor": "prosecutor", "defence": "defence", "judge": "judge", "verdict": "judge"}


def _so(agent, prompt, model):
    """Call an agent and return its typed structured output."""
    return agent(prompt, structured_output_model=model).structured_output


def _case_text(c: Case) -> str:
    opts = f"\nOptions: {', '.join(c.options)}" if c.options else ""
    key = f"\nAnswer key (from the book): {c.correct_answer}" if c.correct_answer else ""
    return (f"Subject: {c.subject}{' (grade ' + c.grade + ')' if c.grade else ''}\n"
            f"Question: {c.question}{opts}{key}\n"
            f"Child's answer: {c.student_answer}\n"
            f"Child's explanation: \"{c.student_why or '(no explanation given)'}\""
            + (f"\nThe class textbook (the court's law book): {c.book_ref}" if c.book_ref else "")
            + (f"\nCase history: in earlier trials this child was shown to hold: "
               + "; ".join(f'"{h}"' for h in c.history) + ". Consider these first, but judge only today's words."
               if c.history else "")
            + (f"\n\nThe court's Rule Book of known wrong ideas for {t} (id: idea):\n{rulebook.book_text(t)}"
               if (t := rulebook.topic_of(c.options, c.question)) else ""))


# ---------------- intake (outside the trial) ----------------

def read_homework(image_bytes: Optional[bytes] = None, image_format: str = "jpeg", text: str = "") -> tuple[list[Case], str]:
    content = [{"text": "Read this homework. " + (f"Typed homework:\n{text}" if text else "")}]
    if image_bytes:
        content.append({"image": {"format": image_format, "source": {"bytes": image_bytes}}})
    page: HomeworkPage = _so(agents.homework_reader(), content, HomeworkPage)
    cases = []
    for i in page.items:
        if not i.question.strip():
            continue
        # Screened here, one item at a time: private details hidden, public names in schoolwork kept.
        joined, _ = screen_child_text(f"{i.question}\n@@\n{i.student_answer}\n@@\n{i.student_reason}")
        parts = joined.split("\n@@\n")
        q, ans, why = parts if len(parts) == 3 else (i.question, i.student_answer, i.student_reason)
        ans, why = _split_reason(q, ans.strip(), why.strip())
        cases.append(Case(case_id=uuid.uuid4().hex[:8], subject=i.subject, question=q.strip(),
                          options=i.options or _choices_in(q, ans), student_answer=ans, student_why=why,
                          source="homework"))   # a question the child has not answered yet is kept:
    # the court asks "what do you think, and why?" instead of a dead end
    return cases, page.unreadable_notes


def _split_reason(question: str, answer: str, why: str) -> tuple[str, str]:
    """Keep the reason out of the answer box (measured: 'because X was assassinated' sat in the answer, the reason
    was empty, and the court asked a child who had explained themselves to explain)."""
    if why:
        return answer, why
    m = re.match(r"^(.*?)[\s,;:-]*\bbecause\b\s*(.+)$", answer, flags=re.I | re.S)
    if m:
        return (m.group(1).strip() or m.group(2).strip()), "because " + m.group(2).strip()
    if re.match(r"^\s*(why|how come|explain)\b", question, flags=re.I) and len(answer.split()) > 3:
        return answer, answer          # the answer to a why-question is the child's reason
    return answer, why


def _choices_in(question: str, answer: str) -> list[str]:
    """'Which is bigger: 3/5 or 2/4?' has two choices even when they are not listed separately on the page.
    Used when the child's answer is one of them, or when they have not answered yet (they will pick)."""
    # "or" in every language the court speaks: Hindi या, French ou, Spanish o, Swahili au, Tamil அல்லது.
    m = re.search(r"([\w./-]+)\s+(?:or|या|ou|o|au|அல்லது)\s+([\w./-]+)\s*[?？।]*\s*$", question.strip())
    choices = [m[1].strip(".?"), m[2].strip(".?")] if m else []
    if not choices:
        # Two numbers to compare, in any language ("कौन बड़ा है: 3/4 या 2/3?" read with the options left out).
        nums = re.findall(r"(?<![\w/.])-?\d+(?:[./]\d+)?(?![\w/])", question)
        if len(nums) == 2 and rulebook.topic_of(nums, question):
            choices = nums
    return choices if not answer.strip() or answer.strip() in choices else []


# ---------------- the hearing graph ----------------

def _ruled(node: str, *decisions: str):
    """Edge condition: follow this edge only if `node` filed one of `decisions`."""
    def cond(state, *, invocation_state=None, **kwargs) -> bool:
        rec = ((invocation_state or {}).get("court") or {}).get(node) or {}
        return rec.get("decision") in decisions
    cond.__name__ = f"{node}_ruled_{'_or_'.join(decisions)}"
    return cond


def _witnesses_found(state, *, invocation_state=None, **kwargs) -> bool:
    return bool(((invocation_state or {}).get("court") or {}).get("witnesses"))


SESSIONS = os.getenv("WHYCOURT_SESSIONS", "data/sessions")
SESSION_BUCKET = os.getenv("WHYCOURT_SESSION_BUCKET", "")


def _session_manager(session_id: str):
    """Where a paused trial is kept: an S3 bucket in the cloud (any server can resume it), else local files."""
    if SESSION_BUCKET:
        from strands.session.s3_session_manager import S3SessionManager
        return S3SessionManager(session_id=session_id, bucket=SESSION_BUCKET, prefix="whycourt/sessions/",
                                region_name=os.getenv("AWS_REGION", "us-east-1"))
    return FileSessionManager(session_id=session_id, storage_dir=SESSIONS)


def build_hearing(use_defence: bool = True, witness_builder: bool = True, session_id: str = "", examiner: bool = True,
                  hearing: bool = True):
    # A child is waiting: no court member may take more than 2 minutes (a hung hearing once took 7).
    timeout = float(os.getenv("WHYCOURT_NODE_TIMEOUT", "120"))
    b = GraphBuilder()
    b.add_node(agents.clerk(), "clerk")
    if not hearing:
        # A question the court cannot test with a witness: the Clerk checks the answer, then the Coach gives
        # feedback on the reason (in _finish). Measured: a full hearing here made a child wait ~77 s for "can't test".
        b.set_entry_point("clerk")
        b.set_execution_timeout(float(os.getenv("WHYCOURT_TRIAL_TIMEOUT", "600")))
        b.set_node_timeout(timeout)
        b.set_hook_providers([CourtOfficers(), Timekeeper()])
        if session_id:
            b.set_session_manager(_session_manager(f"trial-{session_id}"))
        return b.build()
    if use_defence:
        hearing = Swarm([agents.prosecutor(), agents.defence()], max_handoffs=3, max_iterations=4,
                        execution_timeout=2 * timeout, node_timeout=timeout, id="hearing")
        b.add_node(hearing, "hearing")
    else:
        b.add_node(agents.prosecutor(), "hearing")
    b.add_node(agents.judge(), "judge")
    if examiner:
        b.add_node(agents.examiner(), "examiner")
    if witness_builder:    # Rule Book ideas get an exact lesson (lessons.py); the Tutor writes one only outside the book
        b.add_node(agents.tutor_node(), "tutor")
    b.add_edge("clerk", "hearing", condition=_ruled("clerk", "trial"))
    b.add_edge("hearing", "judge")
    if witness_builder:
        b.add_node(agents.witness_builder(), "witness_builder")
        b.add_edge("judge", "witness_builder", condition=_ruled("judge", "cross_examine"))
        b.add_edge("witness_builder", "examiner", condition=_witnesses_found)
    elif examiner:
        b.add_edge("judge", "examiner", condition=_ruled("judge", "cross_examine"))
    if witness_builder:
        b.add_edge("examiner", "tutor", condition=_ruled("examiner", "misconception_found"))
    b.set_entry_point("clerk")
    b.set_max_node_executions(10)
    b.set_execution_timeout(float(os.getenv("WHYCOURT_TRIAL_TIMEOUT", "600")))
    b.set_node_timeout(timeout)
    b.set_hook_providers([CourtOfficers(), Timekeeper()])
    if session_id:
        b.set_session_manager(_session_manager(f"trial-{session_id}"))
    return b.build()


# ---------------- trial lifecycle ----------------

# A paused Graph is rebuilt from its session on disk; the court record travels with the trial itself.


def new_trial(case: Case, lang: str = "English") -> dict:
    why, blocked = screen_child_text(case.student_why)  # personal details removed before any agent reads it
    case = case.model_copy(update={"student_why": why})
    return {"blocked": blocked, "trial_id": uuid.uuid4().hex[:10], "case": case.model_dump(), "transcript": [],
            "lang": language(lang), "status": "open",
            "witness": None, "witness_queue": [], "witness_answers": [], "misconception": None, "objections": 0}


def _say(trial: dict, speaker: str, text: str, checked: bool = False, **extra):
    if not text:
        return
    text = text if checked else kind_words(speaker, text)
    lang = trial.get("lang", "English")
    if speaker != "student" and lang != "English":   # the child's own words are never rewritten
        text = translate(text, lang)
        extra = {k: (translate(v, lang) if k in ("title", "try_this", "witness_question") and isinstance(v, str) else v)
                 for k, v in extra.items()}
    trial["transcript"].append({"speaker": speaker, "text": text, **extra})


def _public_record(court: dict) -> dict:
    """The court record without the (large, rebuildable) witness question table, or the live feed."""
    out = {k: v for k, v in court.items() if k != "witness_plan" and not k.startswith("_")}
    plan = court.get("witness_plan")
    if plan:
        out["witness_plan"] = ({**plan, "state": rulebook.slim(plan["state"])} if plan["kind"] == "book" else plan)
    return out


# What the waiting child sees while the court works: fixed lines keyed by who is working and what they filed.
# Never a model's own words: a ruling written for the record could give away what the witness is about to test.
LIVE_START = {"clerk": ("clerk", "The Clerk checks your answer"), "hearing": ("prosecutor", "The Prosecutor reads your reason"),
              "judge": ("judge", "The Judge decides"), "examiner": ("judge", "The Judge picks a surprise witness"),
              "coach": ("clerk", "The court looks closely at your reason")}
LIVE_RULED = {("clerk", "trial"): "Right answer! Now the court checks your reason.",
              ("clerk", "wrong_answer"): "Hmm, let's look at that answer again.",
              ("prosecutor", "charge"): "I think a sneaky idea might be hiding in this reason!",
              ("prosecutor", "no_case"): "I can't find anything wrong with this reason.",
              ("defence", "sound"): "I'm on your side: this reason makes sense to me!",
              ("defence", "doubtful"): "I'm on your side. Let's test it fairly!",
              ("judge", "cross_examine"): "Let's test it! The court calls a surprise witness.",
              ("judge", "case_closed"): "The court has heard enough!"}


def live_feed(save) -> callable:
    """A court['_live'] callback: turns hook events into the lines above and hands the list to save(lines)."""
    lines: list[dict] = []

    def on(kind: str, who: str, what: str = "") -> None:
        if kind == "start" and who in LIVE_START:
            speaker, text = LIVE_START[who]
            lines.append({"kind": "working", "speaker": speaker, "text": text})
        elif kind == "ruled" and (who, what) in LIVE_RULED:
            lines.append({"kind": "said", "speaker": who, "text": LIVE_RULED[(who, what)]})
            if who == "prosecutor":       # the Swarm hands over: the Defence answers the charge next
                lines.append({"kind": "working", "speaker": "defence", "text": "The Defence prepares"})
        else:
            return
        save(list(lines))
    return on


def hold_trial(trial: dict, use_defence: bool = True, live=None) -> dict:
    if trial.pop("blocked", False):
        _say(trial, "clerk", "The court can't use that message. Let's keep our court kind and safe. Try again in your own words!")
        trial["status"] = "explain_again"
        return trial
    case = Case(**trial["case"])
    court: dict = {"_live": live} if live else {}
    trial["court_record"] = court
    # The Usher (a hook before the Clerk) reads only student_why; the Narrator (a hook after the Judge) reads only
    # student_why and the decisions. Everyone else gets the whole case.
    court["case"] = {"question": case.question, "options": case.options, "student_answer": case.student_answer,
                     "student_why": case.student_why, "correct_answer": case.correct_answer,
                     "book_id": case.book_id, "chapter_id": case.chapter_id}
    trial["use_defence"], trial["session"] = use_defence, f"{trial['trial_id']}-{trial['objections']}"
    court["seed"] = trial["session"]      # varies the witness questions between a trial and its objection re-trial
    return _run(trial, _graph_for(trial), court, _case_text(case))


def _graph_for(trial: dict):
    in_book = bool(rulebook.topic_of(trial["case"]["options"], trial["case"]["question"]))
    # Outside the Rule Book the Witness Builder is experimental: measured, it made a child wait 60-90 s and almost
    # never found a fair question. By default those trials end at once with honest Reason-check feedback instead.
    builder = not in_book and os.getenv("WHYCOURT_WITNESS_BUILDER", "off") == "on"
    trial["scope"] = "book" if in_book else "builder" if builder else "out"
    return build_hearing(trial.get("use_defence", True), witness_builder=builder, examiner=in_book or builder,
                         session_id=trial["session"], hearing=in_book or builder)


def answer_witness(trial: dict, answer: str) -> dict:
    """The child answered the surprise witness: resume the paused Graph inside call_witness."""
    answer = answer.strip()
    trial["witness_answers"].append(answer)
    _say(trial, "student", answer, witness_answer=True)
    court = trial.get("court_state")
    if not court or not trial.get("pending_interrupts"):
        _say(trial, "judge", "The court had to adjourn and lost its place. Please start this case again!", checked=True)
        trial["status"], trial["witness"] = "case_closed", None
        return trial
    responses = [{"interruptResponse": {"interruptId": i, "response": answer}} for i in trial["pending_interrupts"]]
    return _run(trial, _graph_for(trial), court, responses)


def _run(trial: dict, graph, court: dict, task) -> dict:
    try:
        result = graph(task, invocation_state={"court": court})
    except Exception as e:  # e.g. a node timed out: keep whatever rulings were filed, never crash the trial
        if (court.get("usher") or {}).get("decision") != "no_claim":   # the Usher stopping the Clerk is not an error
            trial["error"] = f"{type(e).__name__}: {e}"
        result = None
    trial["court_record"] = _public_record(court)
    trial["court_state"] = trial["court_record"]   # everything needed to resume (the question table is rebuilt)
    trial["pending_interrupts"] = []
    _tell_hearing(trial, court)
    if trial["status"] in ("help", "explain_again"):
        return trial

    if result is not None and result.status == Status.INTERRUPTED and result.interrupts:
        w = result.interrupts[0].reason or {}
        trial["pending_interrupts"] = [i.id for i in result.interrupts]
        trial["witness_queue"].append({k: w.get(k) for k in ("question", "options", "answer_if_sound", "predictions")})
        # Never the predictions. The question is shown in the child's language; the options stay exactly as checked.
        trial["witness"] = {"question": translate(w.get("question") or "", trial.get("lang", "English")),
                            "options": w.get("options")}
        n = len(trial["witness_queue"])
        _say(trial, "judge", "The court calls a surprise witness!" if n == 1 else "One more witness!", checked=True,
             witness_question=w.get("question"), options=w.get("options"))
        trial["status"] = "awaiting_witness"
        return trial

    trial["witness"] = None
    if trial.get("scope") == "out" and court.get("clerk", {}).get("decision") == "trial":
        if court.get("_live"):
            court["_live"]("start", "coach")
        _say(trial, "judge", "There's no surprise witness for this kind of question yet, so here is the court's "
                             "advice on your reason!", checked=True)
        return _finish(trial, "case_closed", kind="out_of_scope")
    expected = ["clerk"] + (["prosecutor", "judge"] + (["defence"] if trial.get("use_defence", True) else [])
                            if court.get("clerk", {}).get("decision") == "trial" else [])
    trial["missing_rulings"] = [n for n in expected if n not in court]
    if trial.get("error") and not court.get("examiner") and court.get("judge", {}).get("decision") is None:
        # The court got stuck (a node timed out or failed): say so, and never claim the reasoning held up.
        _say(trial, "judge", "The court got stuck this time. Please try again!", checked=True)
        return _finish(trial, "case_closed", kind="no_verdict")
    if court.get("judge", {}).get("decision") != "cross_examine":
        return _finish(trial, "case_closed", kind="held_up")
    verdict = court.get("examiner")
    if not court.get("witness_log") or not verdict:
        # No witness could be found. Inside the Rule Book that means the court cannot decide; outside it, the court
        # cannot test this kind of question yet. Either way it says so honestly, and never "your reasoning holds up".
        in_book = bool(rulebook.topic_of(trial["case"].get("options") or [], trial["case"].get("question", "")))
        _say(trial, "judge", "The court couldn't decide this time. No verdict yet!" if in_book else
             "The court can't test this kind of question with a surprise witness yet.", checked=True)
        return _finish(trial, "case_closed", kind="no_verdict" if in_book else "out_of_scope")
    decision = verdict.get("decision", "not_proven")
    rid = lessons.idea_id(verdict.get("wrong_idea")) if decision == "misconception_found" else ""
    if decision == "misconception_found":
        trial["misconception"] = verdict.get("wrong_idea")
        if rid:
            trial["idea_child"] = translate(lessons.CHILD_IDEA[rid], trial.get("lang", "English"))
            _say(trial, "judge", f"Found it! You were thinking: {lessons.CHILD_IDEA[rid]}. "
                                 "That's a win: now you know!", checked=True)
            lsn = lessons.lesson(rid, trial)       # exact parts, never free text: it cannot restate the idea as a rule
        else:
            _say(trial, "judge", verdict.get("statement") or "The court found a sneaky idea!", checked=True)
            lsn = court.get("reteach")
        if lsn:
            _say(trial, "clerk", lsn["explanation"], checked=bool(rid), title=lsn["title"], try_this=lsn["try_this"],
                 try_this_answer=lsn["try_this_answer"])
        return _finish(trial, "misconception_found", rid=rid)
    _say(trial, "judge", verdict.get("statement") or "Thanks for answering, the court has heard you!", checked=True)
    return _finish(trial, "cleared" if decision == "cleared" else "case_closed",
                   kind=None if decision == "cleared" else "no_verdict")


def _finish(trial: dict, status: str, kind: str | None = None, rid: str = "") -> dict:
    """Close the trial with something the child can learn from: an insight, or feedback on their reason."""
    prior = trial.get("prior_finding")
    if prior and status != "cleared" and not (status == "misconception_found" and rid and rid != prior):
        # (A different idea proven by the new answers is the new finding: naming both at once confused a child.)
        # An objection can only overturn a proven idea by the child's answers clearing them; repeating the idea, or
        # a hearing that cannot decide, leaves the earlier finding standing.
        status, rid = "misconception_found", prior
        trial["misconception"] = rulebook.RULES[prior][1]
        trial["idea_child"] = translate(lessons.CHILD_IDEA[prior], trial.get("lang", "English"))
        _say(trial, "judge", f"The court heard your objection. Your answers still show: {lessons.CHILD_IDEA[prior]}.",
             checked=True)
        kind = None
    trial["status"] = status
    trial["verdict_kind"] = kind if status == "case_closed" else None
    decision = {"misconception_found": "misconception_found", "cleared": "cleared"}.get(status, "not_proven")
    info = lessons.insight(trial, decision, rid)
    if kind in ("held_up", "out_of_scope") or (status == "cleared" and not info):
        trial["feedback"] = reason_feedback(trial)
    if info:
        trial["insight"] = {k: ([translate(p, trial.get("lang", "English")) for p in v] if isinstance(v, list)
                                else translate(v, trial.get("lang", "English")) if k != "next" else v)
                            for k, v in info.items()}
    if trial.get("feedback"):
        trial["feedback"] = {k: translate(v, trial.get("lang", "English")) for k, v in trial["feedback"].items()}
    return trial


def reason_feedback(trial: dict) -> dict:
    """Feedback on the child's reason when the court cannot run a witness (or the reason held up): the Coach agent."""
    from .schemas import ReasonFeedback
    case = Case(**trial["case"])
    try:
        out = agents.coach()(_case_text(case) + "\nGive feedback on the child's reason.",
                             structured_output_model=ReasonFeedback).structured_output
        # The screen already labels each part ("Try this"): a model often repeats the label in the text.
        label = re.compile(r"^\s*(try this|think about|what you did well|good job|well done)\s*[:\-–]\s*", re.I)
        return {k: label.sub("", v).strip() for k, v in out.model_dump().items()}
    except Exception:  # feedback is a bonus: never break the verdict for it
        return {}


def _tell_hearing(trial: dict, court: dict) -> None:
    """The first time the Graph returns, tell the child what happened in the hearing (once)."""
    if trial.get("heard"):
        return
    trial["heard"] = True
    usher = court.get("usher", {})
    if usher and usher.get("decision") != "has_claim":
        _say(trial, "clerk", usher.get("statement") or "The court would love to hear how you knew!", checked=True)
        trial["status"] = "explain_again"
        return
    clerk = court.get("clerk", {})
    # Sending a case to trial needs no words of the Clerk's own: a model "being helpful" here once told the child
    # the very thing the surprise witness was about to test. Its wording stays in the record for the teacher.
    opening = "The court is now in session!" if clerk.get("decision") == "trial" else clerk.get("statement", "")
    if trial.get("scope") == "out" and clerk.get("decision") == "trial":
        opening = "Right answer! Let's look at your reason."
    _say(trial, "clerk", opening, checked=True)
    if clerk.get("decision") == "wrong_answer":
        trial["status"] = "help"
        return
    if clerk.get("decision") != "trial":
        trial["status"] = "explain_again"
        return
    if "judge" not in court:     # no hearing ran (a question the court cannot test with a witness)
        return
    pro, dfn, jdg = court.get("prosecutor", {}), court.get("defence", {}), court.get("judge", {})
    # Lines for the child were written by the Narrator hook, which saw only decisions and the child's words.
    lines = CourtLines(**(court.get("lines") or {}))
    # The evidence box shows the child's own words, not the Prosecutor's label for them.
    # (The Prosecutor's own evidence field mixes the child's words with its test question, and once lost a quote mark.)
    _say(trial, "prosecutor", lines.prosecutor, evidence=(trial["case"].get("student_why") or "").strip())
    if dfn:
        _say(trial, "defence", lines.defence, finding=dfn.get("decision"))
    _say(trial, "judge", lines.judge, ruling=jdg.get("decision"))
    if jdg.get("decision") == "cross_examine":
        trial["misconception"] = None


def object_(trial: dict, new_why: str, live=None) -> dict:
    """'I object!' The child explains again and the court re-hears the case."""
    trial["pending_interrupts"] = []
    new_why, trial["blocked"] = screen_child_text(new_why)
    trial["case"]["student_why"] = new_why
    trial["objections"] += 1
    trial["witness"], trial["witness_queue"], trial["witness_answers"] = None, [], []
    if trial.get("status") == "misconception_found":     # what the objection has to overturn
        trial["prior_finding"] = lessons.idea_id(trial.get("misconception")) or trial.get("prior_finding")
    for k in ("heard", "insight", "feedback", "verdict_kind", "idea_child"):
        trial.pop(k, None)
    _say(trial, "student", new_why, objection=True)
    return hold_trial(trial, trial.get("use_defence", True), live)


_PUBLIC = ("trial_id", "status", "transcript", "witness", "witness_answers", "misconception", "objections", "lang",
           "idea_child", "insight", "feedback", "verdict_kind", "teach")
_PUBLIC_CASE = ("question", "options", "student_answer", "student_why", "subject", "grade")


def public_view(trial: dict) -> dict:
    """What the child's screen receives: an allow-list. Never the answer key, the witness predictions, the court
    record, practice answers, error text or anything else internal."""
    out = {k: trial[k] for k in _PUBLIC if k in trial}
    out["case"] = {k: v for k, v in (trial.get("case") or {}).items() if k in _PUBLIC_CASE}
    return out


_PLAN_NUM = re.compile(r"-?\d+(?:[./]\d+)?")


def _plan_examples(found: list[dict]) -> dict[str, list[dict]]:
    """For each Rule Book idea found, example questions on which that idea gives the WRONG answer (acted out in the
    sandbox). A reteach example where the wrong idea happens to work would teach the idea (measured: a plan used
    3/4 vs 2/3, where 'the bigger top number wins' gives the right answer)."""
    out = {}
    for t in found:
        rid = lessons.idea_id(t.get("misconception"))
        if rid and rid not in out:
            out[rid] = lessons._counter_examples(rid, set(), 3, "plan-" + rid)
    return out


def _plan_numbers_ok(plan: str, allowed: set[str]) -> list[str]:
    """Numbers in the plan that are not in a checked example (a made-up example may confirm the wrong idea)."""
    return sorted({n for n in _PLAN_NUM.findall(plan) if "/" in n or "." in n or n.startswith("-")} - allowed)


def teacher_summary(trials: list[dict]) -> str:
    found = [t for t in trials if t["status"] == "misconception_found"]
    if not found:
        return "No confirmed hidden misconceptions yet."
    examples = _plan_examples(found)
    lines = "\n".join(f"- {t['case']['subject']}: {t['misconception']} (question: {t['case']['question']})" for t in found)
    checked = "\n".join(f"- for '{rulebook.RULES[rid][1]}': " + "; ".join(
        f"{q['question']} (the wrong idea picks {q['idea_pick']}, the right answer is {q['correct']})" for q in qs)
        for rid, qs in examples.items())
    allowed = {n for qs in examples.values() for q in qs for n in _PLAN_NUM.findall(q["question"] + " " + " ".join(q["options"]))}
    allowed |= {n for t in found for n in _PLAN_NUM.findall(t["case"]["question"] + " " + " ".join(t["case"].get("options") or []))}
    task = f"Confirmed hidden misconceptions:\n{lines}"
    if checked:
        task += ("\n\nChecked examples (on each one the wrong idea gives the WRONG answer, so it shows the idea "
                 f"failing). Use ONLY these numbers in your examples, never make up your own:\n{checked}")
    for _ in range(2):
        plan = str(agents.teacher_agent()(task))
        bad = _plan_numbers_ok(plan, allowed) if examples else []
        if not bad:
            return plan
        task += f"\n\nYour last plan used numbers that were not checked ({', '.join(bad)}). Use only the checked examples."
    # Still made-up numbers: an exact plan from the checked examples instead.
    out = []
    for rid, qs in examples.items():
        out.append(f"### {lessons.CHILD_IDEA[rid].capitalize()}\n" + f"- Remember: {lessons.REMEMBER[rid]}\n" +
                   "\n".join(f"- Ask: {q['question']} (the idea picks {q['idea_pick']}; the answer is {q['correct']})"
                              for q in qs))
    return "\n\n".join(out)


def teach(trial: dict) -> dict:
    """'Teach me' after a wrong answer: the Explainer starts from the child's reason; the Expert checks the lesson."""
    if trial.get("teach"):
        return trial["teach"]
    lang = trial.get("lang", "English")
    c = trial["case"]
    topic = rulebook.topic_of(c.get("options") or [], c.get("question", ""))
    if topic:
        # A Rule Book question: the right answer and why are worked out exactly (fast, and never wrong).
        from .practice import why
        from .sandbox import act_out_batch
        q = {"question": c["question"], "options": c["options"]}
        right = act_out_batch({"s": rulebook.SOUND_CODES[topic]}, [q])["s"][c["question"].strip()]
        others = lessons._counter_examples(next(r for r, v in rulebook.RULES.items() if v[0] == topic), {c["question"]},
                                           1, trial["trial_id"] + "-teach")
        sound = rulebook.SOUND_CODES[topic]
        tq = others[0] if others else q
        t_ans = act_out_batch({"s": sound}, [tq])["s"][tq["question"].strip()]
        trial["teach"] = {"title": lessons.TITLES.get(topic, "Lesson"),
                          "explanation": translate(f"The answer is {right}. " + why(topic, c["question"], c["options"], right), lang),
                          "try_this": translate(tq["question"], lang), "try_this_answer": t_ans}
        return trial["teach"]
    case = Case(**trial["case"])
    court: dict = {}
    agents.explainer()(_case_text(case) + "\nThe child's answer is not right yet. Teach them.",
                       invocation_state={"court": court})
    rt = court.get("reteach")
    if not rt:
        return {}
    trial["teach"] = {k: translate(v, lang) if k != "try_this_answer" else v for k, v in rt.items()}
    return trial["teach"]
