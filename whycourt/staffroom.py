"""The staff room: Why Court talks to other agents over the A2A (Agent-to-Agent) protocol.

The Court Reporter is a Strands agent that knows every trial on record. It is served with Strands' A2AServer, so a
teacher's own assistant agent, built by anyone with any A2A-compatible framework, can ask it what the class got
wrong this week and get grouped findings and reteach ideas back. It serves one class, unlocked by that
class's teacher, and only counts leave the court: no names, no court names, no children's words.

  python scripts/staffroom.py serve CODE PIN     # one class's Court Reporter on http://127.0.0.1:9000
  python scripts/staffroom.py ask "..."          # a teacher's assistant agent asks it, over A2A
"""
from __future__ import annotations

import json
import re
from collections import Counter

from strands import Agent, tool

from . import agents, store


def findings(class_code: str) -> dict:
    """One class's confirmed wrong ideas, as counts only: no court names, no children's words."""
    from . import classes
    code = classes.normal_code(class_code)
    trials = store.class_trials(code)
    found = [t for t in trials if t["status"] == "misconception_found"]
    counts = Counter(t.get("misconception") or "?" for t in found)
    return {"class": (classes.get(code) or {}).get("name", ""), "trials": len(trials),
            "reasoning_held": sum(t["status"] == "cleared" or t.get("verdict_kind") == "held_up" for t in trials),
            "confirmed_wrong_ideas": [{"idea": idea, "children": n,
                                       "example_question": next(t["case"]["question"] for t in found
                                                                if t.get("misconception") == idea)}
                                      for idea, n in counts.most_common()],
            "teacher_approved": sum(bool(t.get("teacher_approved")) for t in found)}


def findings_tool(class_code: str):
    """The Court Reporter's one tool, bound to one class when the server starts (it cannot ask for another)."""
    @tool
    def class_findings() -> str:
        """This class's confirmed wrong ideas (counts only, no names or court names) and how many trials held up."""
        return json.dumps(findings(class_code))
    return class_findings


def _no_thinking(text: str) -> str:
    return re.sub(r"<thinking>.*?</thinking>\s*", "", text, flags=re.S).strip()


def court_reporter(class_code: str) -> Agent:
    return agents._agent("court_reporter", agents.PRO, 0.2, """You are the Court Reporter of Why Court, a classroom
game that tests whether children's right answers rest on sound reasons. Other agents (usually a teacher's assistant)
ask you about the class. Call class_findings, then answer briefly: which wrong ideas were confirmed, how many children,
and one two-minute reteach idea for each. Findings are advisory until a teacher approves them; say so.
Never guess beyond the record. You only know this one class, and never anything about individual children.""",
                          [findings_tool(class_code)])


def serve(class_code: str, pin: str, port: int = 9000) -> None:
    """Serve one class's Court Reporter over A2A. The class code and PIN are checked once, here."""
    from strands.multiagent.a2a import A2AServer
    from . import classes
    if not classes.check(class_code, pin):
        raise SystemExit("Wrong class code or PIN: the Court Reporter only serves a class its teacher unlocked.")
    reporter = court_reporter(class_code)
    reporter.description = "Reports which hidden wrong ideas Why Court confirmed in one class, with reteach ideas."
    A2AServer(agent=reporter, port=port, enable_a2a_compliant_streaming=True).serve()


def teachers_assistant(endpoint: str = "http://127.0.0.1:9000") -> Agent:
    """A different agent, in a different process, that reaches the court only through A2A, using the A2A client
    tool vended by Strands itself (allowed to talk to this one endpoint only)."""
    from strands.vended_tools import make_a2a_client
    a2a = make_a2a_client(name="ask_why_court", allowed_endpoints=[endpoint])
    return agents._agent("teachers_assistant", agents.PRO, 0.2, f"""You are a busy teacher's planning assistant.
To learn what the class misunderstands, use ask_why_court to send the Why Court Court Reporter at {endpoint} a
message asking for this class's confirmed wrong ideas and reteach ideas. Then write tomorrow's 10-minute warm-up plan
in 5 short lines.""", [a2a])
