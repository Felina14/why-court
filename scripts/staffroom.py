"""Why Court over A2A. See whycourt/staffroom.py.

  python scripts/staffroom.py serve CLASS_CODE PIN
  python scripts/staffroom.py ask "What should I reteach tomorrow?"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from whycourt import staffroom  # noqa: E402

if __name__ == "__main__":
    if sys.argv[1:2] == ["serve"]:
        if len(sys.argv) < 4:
            raise SystemExit("usage: python scripts/staffroom.py serve CLASS_CODE PIN")
        staffroom.serve(sys.argv[2], sys.argv[3])
    else:
        reply = staffroom.teachers_assistant()(" ".join(sys.argv[2:]) or "What should I reteach tomorrow?")
        print(staffroom._no_thinking(str(reply)))
