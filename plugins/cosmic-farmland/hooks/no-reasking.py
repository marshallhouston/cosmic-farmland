#!/usr/bin/env python3
"""Stop hook: detect re-asking patterns in last assistant message.

Per marshall's CLAUDE.md output discipline #4:
  No "Want me to do X?" prompts when the next action is obvious.
  Just do it. Confirm only on irreversible/destructive operations.

Calibration data showed 10x "yes" / 5x "y" in single sessions. Model keeps asking.
This hook flags it post-hoc so marshall sees the pattern and can correct.

Inputs (stdin JSON from CC):
  - transcript_path: ~/.claude/projects/.../<sid>.jsonl
  - session_id, hook_event_name, etc.

Outputs:
  - stderr: warning to marshall's terminal
  - JSON additionalContext (stdout): reminder injected into model on next turn
  - Append to ~/.claude/cc-friction-log.jsonl for later analysis
"""
import json
import re
import sys
import os
from datetime import datetime, timezone

# patterns that are re-asking when next action would be obvious
PATTERNS = [
    r"\bwant me to\b",
    r"\bshould i\b",
    r"\bdo you want\b",
    r"\bwould you like\b",
    r"\blet me know if you want\b",
    r"\bshall i\b",
    r"\bwant to\b.*\?",
    # bare-prompt patterns surfaced by 2026-04-27 audit:
    # assistant ends a long menu w/ single-word question, user can't tell which item it refers to
    r"(?m)^which\??$",
    r"(?m)^pick\??$",
    r"(?m)^choose\??$",
    r"(?m)^thoughts\?$",
]

# whitelist phrases that legitimately need confirmation (destructive ops, ambiguous scope)
SAFE_CONTEXT = [
    "delete", "drop table", "force push", "rm -rf", "reset --hard",
    "destructive", "irreversible", "uninstall", "revoke",
]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return 0

    # read last assistant message text
    last_text = ""
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        last_text = c.get("text", "")
                        break
            if last_text:
                break
    except Exception:
        return 0

    if not last_text:
        return 0

    text_lower = last_text.lower()
    matches = []
    for pat in PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            matches.append((pat, m.group(0)))

    if not matches:
        return 0

    # if the question is about a destructive op, allow it
    if any(kw in text_lower for kw in SAFE_CONTEXT):
        return 0

    # log violation
    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "re_asking",
                "matches": [m[1] for m in matches],
                "snippet": last_text[-400:],
            }) + "\n")
    except Exception:
        pass

    sys.stderr.write(
        f"[cc-friction] re-asking detected: {', '.join(repr(m[1]) for m in matches)}\n"
        f"[cc-friction] CLAUDE.md output discipline #4: just do obvious next action.\n"
    )
    sys.stderr.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
