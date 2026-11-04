"""OpenTelemetry tracing for the court, through Strands' built-in telemetry.

Every agent invocation, model call, tool call and Graph/Swarm node becomes a span, so a whole trial (including the
pauses for the child's answers) can be followed in any OpenTelemetry viewer: Jaeger, Langfuse, or Amazon CloudWatch
GenAI observability.

  WHYCOURT_TRACE=console   print spans to the terminal
  WHYCOURT_TRACE=otlp      send spans to OTEL_EXPORTER_OTLP_ENDPOINT (needs: pip install 'strands-agents[otel]')
"""
from __future__ import annotations

import os

_done = False


def setup() -> str:
    """Turn tracing on once, as configured. Returns what was set up ('' if off)."""
    global _done
    mode = os.getenv("WHYCOURT_TRACE", "").lower()
    if _done or mode not in ("console", "otlp"):
        return ""
    from strands.telemetry import StrandsTelemetry
    t = StrandsTelemetry()
    if mode == "console":
        t.setup_console_exporter()
    else:
        t.setup_otlp_exporter()
    _done = True
    return mode
