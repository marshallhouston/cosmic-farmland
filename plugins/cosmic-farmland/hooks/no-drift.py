#!/usr/bin/env python3
"""Stop hook: detect marshall-voice drift in last assistant message.

Per CLAUDE.md "Marshall voice + product discipline rules":
  - No "sprint" language. Work continuously by impact.
  - Explicit action verbs in batch confirmations (no bare "apply all" / "proceed").

Logs to ~/.claude/cc-friction-log.jsonl with type=drift for later mining.
"""
import json
import re
import sys
import os
import time
from datetime import datetime, timezone


def read_last_assistant_text(transcript_path: str, max_wait_s: float = 1.0) -> str:
    """Return text of most recent assistant turn.

    Stop hook fires before CC has finished flushing the just-completed assistant
    message in some builds. If the last record in the transcript is type=user,
    the assistant write is still pending — poll briefly, then read.
    """
    deadline = time.monotonic() + max_wait_s
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

# (regex, label) pairs. Case-insensitive.
PATTERNS = [
    (r"\bsprints?\b", "sprint_language"),
    (r"\bnext[- ]sprint\b", "sprint_language"),
    (r"\bthis sprint\b", "sprint_language"),
    # bare batch verbs in numbered/bulleted menus
    (r"(?mi)^\s*[-*\d.)]+\s*(?:apply all|proceed|continue|do it all)\s*$", "batch_verb"),
]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return 0

    last_text = read_last_assistant_text(transcript_path)
    if not last_text:
        return 0

    scan_lower = last_text.lower()

    matches = []
    for pat, label in PATTERNS:
        m = re.search(pat, scan_lower)
        if m:
            matches.append((label, m.group(0)))

    if not matches:
        return 0

    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "drift",
                "labels": sorted({m[0] for m in matches}),
                "matches": [m[1] for m in matches],
                "snippet": last_text[-400:],
            }) + "\n")
    except Exception:
        pass

    labels = sorted({m[0] for m in matches})
    sys.stderr.write(
        f"[cc-friction] drift detected ({', '.join(labels)}): "
        f"{', '.join(repr(m[1]) for m in matches)}\n"
        f"[cc-friction] CLAUDE.md marshall-voice rules: no sprint language, explicit batch verbs.\n"
    )
    sys.stderr.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
