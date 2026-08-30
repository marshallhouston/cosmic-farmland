"""Shared transcript helpers for Stop hooks.

Stop hooks fire before CC has finished flushing the just-completed assistant
message in some builds. If the last record in the transcript is type=user, the
assistant write is still pending, so poll briefly before reading.
"""
import json
import time


def read_last_assistant_text(transcript_path: str, max_wait_s: float = 1.0) -> str:
    """Return text of the most recent assistant turn, or "" if none."""
    deadline = time.monotonic() + max_wait_s
    lines: list = []
    while True:
        try:
            with open(transcript_path) as f:
                lines = f.readlines()
        except Exception:
            return ""

        last_type = None
        for line in reversed(lines):
            try:
                d = json.loads(line)
            except Exception:
                continue
            t = d.get("type")
            if t in ("user", "assistant"):
                last_type = t
                break

        if last_type == "assistant" or time.monotonic() >= deadline:
            break
        time.sleep(0.05)

    for line in reversed(lines):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "assistant":
            continue
        for c in d.get("message", {}).get("content", []):
            if isinstance(c, dict) and c.get("type") == "text":
                txt = c.get("text", "")
                if txt:
                    return txt
    return ""


# A blocking Stop hook re-runs the model in-turn. A bare "revise the output"
# instruction makes it reprint the whole response, so marshall reads the same
# answer twice. The block is what actually changes behavior (48 em-dash and 45
# time-estimate catches in the friction log, ~92% precision), so keep blocking
# and shrink the payload instead: ask for a patch, not a reprint.
PATCH_ONLY = (
    " Do NOT reprint the whole response. Emit ONLY the corrected sentences, "
    "prefixed with 'Correction:'."
)
