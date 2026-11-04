"""Court rules as Strands hooks: one policy, applied to every agent, written once instead of in every prompt.

- CourtRules (on every agent):
    * No conviction without proof: a "misconception_found" verdict is rewritten to "not_proven" unless the child's
      own witness answers prove it, and the idea named is always the one the answers prove.
    * Kindness: every statement an agent files for the child passes the Kindness Officer before it is recorded.
    * Stenographer: every tool call is written into the court record, so a teacher can see who did what and why.
    * Fair test: a charge the Defence could not answer is never closed without a surprise witness.
    * Checked lessons: the exact lesson the Tutor files is read by the Maths Expert agent; a wrong one is sent back.
- CourtOfficers (on the hearing Graph): two agents with a deliberately narrow view, run by hooks so they never
  see more than they should. The Usher runs before the Clerk and sees ONLY the child's reason ("is there a reason at
  all?"); if there is none, the Clerk's node is cancelled. The Narrator runs after the Judge and sees ONLY the
  decisions and the child's words, never the analysis, so the lines it writes for the child cannot spoil the witness.
  (A Graph node would be handed the whole case; a hook decides exactly what each officer reads.)
- Timekeeper (on the hearing Graph): writes the order the court members spoke in, with timings.
"""
from __future__ import annotations

import json
import re
import time

from strands.hooks import (AfterNodeCallEvent, AfterToolCallEvent, BeforeNodeCallEvent, BeforeToolCallEvent,
                           HookProvider, HookRegistry)

from .guardrails import kind_words


def _court(event) -> dict:
    return (event.invocation_state or {}).setdefault("court", {})


CHILD_FACING = {"usher", "clerk", "examiner"}


def _live(event, kind: str, who: str, what: str = "") -> None:
    """Tell the waiting child what the court is doing right now (court['_live'], set by the server)."""
    f = _court(event).get("_live")
    if f:
        try:
            f(kind, who, what)
        except Exception:   # the live feed is a bonus: never break a hearing for it
            pass


def exact_answer_check(case: dict) -> bool | None:
    """True/False when the child's answer can be checked exactly (Rule Book question), else None."""
    from .rulebook import SOUND_CODES, topic_of
    from .sandbox import act_out_batch
    opts, q, ans = case.get("options") or [], case.get("question", ""), str(case.get("student_answer", "")).strip()
    topic = topic_of(opts, q)
    if not topic or not ans:
        return None
    pick = act_out_batch({"s": SOUND_CODES[topic]}, [{"question": q, "options": opts}])["s"][q.strip()]
    return None if pick.startswith("could not run") or pick == "cannot tell" else pick == ans


HINTS = {"fractions": "Not quite yet! Make the pieces the same size first, then compare.",
         "decimals": "Not quite yet! Write both numbers with the same number of digits after the point, then compare.",
         "negatives": "Not quite yet! Picture both numbers on a number line. Which one is further to the right?",
         "multiply_divide": "Not quite yet! Is the number you multiply or divide by bigger or smaller than 1?",
         "floating": "Not quite yet! Think about what the thing is made of, not how big or heavy it is.",
         "a_an": "Not quite yet! Say the next word out loud. Does it start with a vowel sound?",
         "plurals": "Not quite yet! Say the word out loud. How does its ending change for more than one?",
         "past_tense": "Not quite yet! Some verbs change in their own way in the past. Say it in a sentence."}


def _gives_away(case: dict, statement: str) -> bool:
    """Does a hint name the right option (the one the sandbox picks with correct thinking)?"""
    from .rulebook import SOUND_CODES, topic_of
    from .sandbox import act_out_batch
    opts, q = case.get("options") or [], case.get("question", "")
    topic = topic_of(opts, q)
    if not topic:
        return False
    right = act_out_batch({"s": SOUND_CODES[topic]}, [{"question": q, "options": opts}])["s"].get(q.strip(), "")
    return bool(right) and re.search(rf"(?<![\w.\-/]){re.escape(right)}(?![\w/]|\.\d)", statement) is not None


class CourtRules(HookProvider):
    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool)
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] == "verify_witness":
            used = _court(event).setdefault("tool_calls", {})
            used["verify_witness"] = used.get("verify_witness", 0) + 1
            if used["verify_witness"] > 2:
                event.cancel_tool = ("verify_witness budget used up (2 calls). Do not call it again. Call "
                                     "record_witnesses with your best questions now, or stop: the court rules not proven.")
            return
        if event.tool_use["name"] == "record_reteach":
            # The lesson that is filed is the lesson that is checked: the Maths Expert reads exactly these words.
            # (Checking "was the expert consulted?" was not enough: a Tutor once showed it one draft and filed another.)
            from . import agents
            lesson = event.tool_use.get("input") or {}
            court = _court(event)
            tries = court["lesson_checks"] = court.get("lesson_checks", 0) + 1
            fields = "\n".join(f"{k}: {lesson.get(k, '')}" for k in ("title", "explanation", "try_this", "try_this_answer"))
            report = str(agents.maths_expert()(
                "Check this lesson for a child, exactly as it will be shown. End with one line: "
                "VERDICT: CORRECT or VERDICT: WRONG.\n\n" + fields))
            court.setdefault("stenographer", []).append({"agent": "maths_expert", "tool": "check_filed_lesson",
                                                         "input": fields[:400], "result": report[-400:], "status": ""})
            if "VERDICT: CORRECT" not in report.upper():
                event.cancel_tool = (
                    "Court rule: the Maths Expert found a mistake in the lesson you filed. Fix it and file again.\n"
                    + report[-1500:] if tries < 3 else
                    "Court rule: the lesson could not be made correct, so no lesson is shown. Stop.")
            return
        if event.tool_use["name"] != "record_ruling":
            return
        args = dict(event.tool_use.get("input") or {})
        agent = event.agent.name
        if agent == "clerk":
            # Where the right answer can be worked out exactly (a Rule Book question), the Clerk cannot get it wrong:
            # measured, a Clerk whose own calculator said "3/5 > 2/4 is True" still filed wrong_answer for 3/5.
            truth = exact_answer_check(_court(event).get("case") or {})
            wanted = {True: "trial", False: "wrong_answer"}.get(truth)
            if wanted and str(args.get("decision", "")).strip().lower() != wanted:
                _court(event).setdefault("overruled", []).append(
                    f"clerk said {args.get('decision')}, but the answer is exactly {'right' if truth else 'wrong'}")
                args["decision"] = wanted
                args["statement"] = "The court is now in session!" if truth else \
                    "Not quite yet! Look again carefully, then tell the court why."
            if truth is False and _gives_away(_court(event).get("case") or {}, str(args.get("statement", ""))):
                # A hint must leave the thinking to the child: measured, "0.5 is the same as 0.50, which is bigger
                # than 0.45" told them the answer. The worked answer is for "Teach me".
                from .rulebook import topic_of
                case = _court(event).get("case") or {}
                args["statement"] = HINTS.get(topic_of(case.get("options") or [], case.get("question", "")),
                                              "Not quite yet! Look again carefully, then tell the court why.")
        if agent == "judge" and _court(event).get("judge_overruled") and "judge" in _court(event):
            # Measured: an overruled Judge kept re-filing case_closed (26 times) until its node timed out.
            event.cancel_tool = ("Your ruling is already filed: the court rules send this case to the witness stand, "
                                 "where a child who understands is cleared. Do not call record_ruling again. "
                                 "Reply with one short sentence and stop.")
            return
        if agent == "judge" and str(args.get("decision", "")).strip().lower() == "case_closed":
            # A charge the Defence could not answer is never closed untested: the witness costs the child nothing
            # and cannot convict anyone by itself. (Measured: the Judge closed charged cases in most live runs.)
            # For Rule Book topics the Defence's "sound" does not close it either: one example where the child's
            # rule works cannot show it works in general (that is exactly how a wrong idea hides; measured on
            # frac-04), while the witnesses test it properly and clear a child who understands.
            from .rulebook import topic_of
            court = _court(event)
            case = court.get("case") or {}
            charged = (court.get("prosecutor") or {}).get("decision") == "charge"
            in_book = bool(topic_of(case.get("options") or [], case.get("question", "")))
            # A Rule Book question is always tested, even when the Prosecutor files no_case: a right answer can hide
            # a wrong idea (measured on frac-04: the Prosecutor filed no_case and the idea went uncaught).
            if in_book or (charged and (court.get("defence") or {}).get("decision") != "sound"):
                args["decision"] = "cross_examine"
                args["wrong_idea"] = args.get("wrong_idea") or (court.get("prosecutor") or {}).get("wrong_idea", "")
                court.setdefault("overruled", []).append(
                    "judge said case_closed on a charge the witnesses had not tested; the court tests it instead")
                court["judge_overruled"] = True
        if agent == "examiner":
            from .witness import pending, proof
            if _court(event).get("witness_log") and pending(_court(event)) is not None:
                # A verdict before the court has heard enough is not filed: the Examiner is sent back to the stand.
                # (Measured: an Examiner ruled after one witness on frac-01, so a provable idea went unproven.)
                _court(event).setdefault("overruled", []).append("examiner ruled before the court had heard enough")
                event.cancel_tool = ("Court rule: the court has not heard enough yet. Call call_witness again, and "
                                     "only file your verdict when call_witness says the court has heard enough.")
                return
            proven, idea = proof(_court(event))
            if str(args.get("decision", "")).strip().lower() == "misconception_found":
                if proven != "misconception_found":
                    args["decision"] = "not_proven"
                    args["statement"] = "The court has not proven anything today. You go free!"
                    _court(event).setdefault("overruled", []).append(
                        f"examiner said misconception_found, but the answers prove {proven}")
                else:
                    args["wrong_idea"] = idea
        # Only statements the child actually reads go to the Kindness Officer. The Prosecutor's, Defence's and
        # Judge's own statements stay in the court record; the Narrator writes their lines for the child (and those
        # are checked when spoken). That saved 3-4 Nova calls per trial.
        # The Usher's "has_claim" and the Clerk's "trial" are never read out (the child sees a fixed line instead):
        # skipping them saves two Nova calls before the first thing the child sees (measured 3.5 s).
        unseen = (agent, str(args.get("decision", "")).strip().lower()) in (("usher", "has_claim"), ("clerk", "trial"))
        if args.get("statement") and agent in CHILD_FACING and not unseen:
            args["statement"] = kind_words(agent, args["statement"])
        event.tool_use = {**event.tool_use, "input": args}

    def after_tool(self, event: AfterToolCallEvent) -> None:
        result = event.result or {}
        text = " ".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict))
        if event.tool_use["name"] == "verify_witness" and result.get("status") != "error":
            # Keep the Verifier's report against the question it audited: record_witnesses only accepts a
            # witness question the Verifier passed.
            sent = str((event.tool_use.get("input") or {}).get("input", ""))
            q = next((ln.split(":", 1)[1].strip() for ln in sent.splitlines() if ln.lower().startswith("question:")), "")
            _court(event).setdefault("verifications", []).append({"question": q, "report": text})
        if event.tool_use["name"] == "record_ruling" and getattr(event.agent, "name", "") == "judge" \
                and _court(event).get("judge_overruled") and result.get("status") != "error":
            # Tell the overruled Judge plainly that the ruling stands, so it does not keep re-filing case_closed.
            event.result = {**result, "content": [{"text": "Recorded judge: cross_examine. The court rules send an "
                            "untested charge to the witness stand instead of closing it; your ruling is filed and "
                            "your work is done. Do not call record_ruling again."}]}
        if event.tool_use["name"] == "record_ruling" and text.startswith("Recorded") and \
                getattr(event.agent, "name", "") in ("prosecutor", "defence"):
            _live(event, "ruled", event.agent.name, (_court(event).get(event.agent.name) or {}).get("decision", ""))
        _court(event).setdefault("stenographer", []).append({
            "agent": event.agent.name, "tool": event.tool_use["name"],
            "input": json.dumps(event.tool_use.get("input"), default=str)[:400], "result": text[:400],
            "status": result.get("status", "")})


class CourtOfficers(HookProvider):
    """Graph-level hook running the Usher (before the Clerk) and the Narrator (after the Judge)."""

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeNodeCallEvent, self.usher)
        registry.add_callback(AfterNodeCallEvent, self.narrator)

    def usher(self, event: BeforeNodeCallEvent) -> None:
        if event.node_id != "clerk":
            return
        from . import agents
        court = _court(event)
        if exact_answer_check(court.get("case") or {}) is False:
            # An answer that is exactly wrong goes straight to the Clerk for a hint, with or without a reason:
            # asking "why?" again would never tell the child the answer is wrong (measured: a Library exercise
            # looped on "Tell the court why!").
            court["usher"] = {"decision": "has_claim", "statement": "", "wrong_idea": "", "evidence": "",
                              "suspects": [], "skipped": "the answer is exactly wrong: the Clerk gives a hint"}
            return
        why = (court.get("case") or {}).get("student_why", "")
        agents.usher()(f'Child\'s reason: "{why}"', invocation_state={"court": court})
        if (court.get("usher") or {}).get("decision") != "has_claim":
            event.cancel_node = "The Usher found no reason to hear: the child is asked to explain first."

    def narrator(self, event: AfterNodeCallEvent) -> None:
        if event.node_id != "judge":
            return
        from . import agents
        from .schemas import CourtLines
        court = _court(event)
        why = (court.get("case") or {}).get("student_why", "")
        cast = {k: court[k].get("decision") for k in ("prosecutor", "defence", "judge") if k in court}
        # Tell the Narrator what really comes next, so the Judge never promises a witness the court cannot call.
        import os
        from .rulebook import topic_of
        case = court.get("case") or {}
        witness = bool(topic_of(case.get("options") or [], case.get("question", ""))) or \
            os.getenv("WHYCOURT_WITNESS_BUILDER", "off") == "on"
        nxt = ("a surprise witness" if witness else "feedback on the child's reason (no witness)") \
            if cast.get("judge") == "cross_examine" else "the case is closed"
        lines = agents.narrator()(f'Child\'s words: "{why}"\nDecisions: {cast}\nWhat happens next: {nxt}',
                                  structured_output_model=CourtLines).structured_output
        court["lines"] = lines.model_dump()


class Timekeeper(HookProvider):
    """Graph-level hook: the order the court members were heard in."""

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeNodeCallEvent, self.before)
        registry.add_callback(AfterNodeCallEvent, self.after)

    def before(self, event: BeforeNodeCallEvent) -> None:
        _court(event).setdefault("timeline", []).append({"node": event.node_id, "start": time.time()})
        _live(event, "start", event.node_id)

    def after(self, event: AfterNodeCallEvent) -> None:
        if event.node_id in ("clerk", "judge"):
            _live(event, "ruled", event.node_id, (_court(event).get(event.node_id) or {}).get("decision", ""))
        for t in reversed(_court(event).get("timeline", [])):
            if t["node"] == event.node_id and "seconds" not in t:
                t["seconds"] = round(time.time() - t["start"], 1)
                break
