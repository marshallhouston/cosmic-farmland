#!/usr/bin/env python3
"""Stop hook: detect marshall-voice drift in last assistant message.

Per CLAUDE.md "Marshall voice + product discipline rules":
  - No "sprint" language. Work continuously by impact.
  - No time estimates in days/weeks/hours for scope.
  - Explicit action verbs in batch confirmations (no bare "apply all" / "proceed").

Logs to ~/.claude/cc-friction-log.jsonl with type=drift for later mining.
"""
import json
import re
import sys
import os
from datetime import datetime, timezone

# (regex, label) pairs. Case-insensitive.
PATTERNS = [
    (r"\bsprints?\b", "sprint_language"),
    (r"\bnext[- ]sprint\b", "sprint_language"),
    (r"\bthis sprint\b", "sprint_language"),
    # time estimates: "~2 days", "about 3 weeks", "takes 4 hours", "1-2 days"
    (r"\b(?:~|about |around |roughly |takes? |estimate[sd]? |approx(?:imately)? )?\d+(?:\s*[-–]\s*\d+)?\s*(?:day|week|hour)s?\b", "time_estimate"),
    # bare batch verbs in numbered/bulleted menus
    (r"(?mi)^\s*[-*\d.)]+\s*(?:apply all|proceed|continue|do it all)\s*$", "batch_verb"),
]

# allow time references in code blocks, dates, file paths, log timestamps
SAFE_CONTEXT = [
    "ago", "yesterday", "tomorrow",  # relative refs are fine
    "cleanupperiod",  # config keys
    "ttl", "timeout", "retention",
]


def strip_code_blocks(text: str) -> str:
    """Drop fenced code blocks + inline code so we don't flag legit code."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", "", text)
    return text


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return 0

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

    scan_text = strip_code_blocks(last_text)
    scan_lower = scan_text.lower()

    matches = []
    for pat, label in PATTERNS:
        m = re.search(pat, scan_lower)
        if m:
            window_start = max(0, m.start() - 30)
            window_end = min(len(scan_lower), m.end() + 30)
            window = scan_lower[window_start:window_end]
            if any(kw in window for kw in SAFE_CONTEXT):
                continue
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
        f"[cc-friction] CLAUDE.md marshall-voice rules: no sprint, no time estimates, explicit batch verbs.\n"
    )
    sys.stderr.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
