#!/usr/bin/env python3
"""Stop hook: detect em-dashes / en-dashes in last assistant message.

Per marshall's house style: never use em-dashes or en-dashes in output.
Use hyphens or rewrite the sentence.

Calibration: the model reaches for "X - Y" em-dash framing constantly even
when told not to. The rule lived nowhere in the system prompt, so nothing
caught it. This hook closes the loop post-hoc.

Inputs (stdin JSON from CC):
  - transcript_path: ~/.claude/projects/.../<sid>.jsonl
  - session_id, hook_event_name, etc.

Outputs:
  - stderr: warning to marshall's terminal
  - JSON {decision: block, reason: ...} on stdout: blocks Stop, forces model
    to revise output in-turn with corrective feedback.
  - Append to ~/.claude/cc-friction-log.jsonl for later analysis

Safe zones (NOT linted): fenced code blocks, inline code spans, quoted spans,
and blockquote lines. Quoting / code is citation -- a dash inside a quoted
source string or a code sample is reproducing, not authoring.
"""
import json
import re
import sys
import os
from datetime import datetime, timezone

from _transcript import PATCH_ONLY, read_last_assistant_text


# Em-dash (U+2014) and en-dash (U+2013). The hyphen-minus is fine.
DASH_PATTERN = re.compile("[—–]")


def strip_safe_zones(text: str) -> str:
    # Drop fenced code blocks.
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Drop inline code spans.
    text = re.sub(r"`[^`\n]*`", "", text)
    # Drop quoted spans (straight + curly double quotes) -- citation, not authoring.
    text = re.sub(r"\"[^\"\n]{0,200}\"", "", text)
    text = re.sub("[“][^“”\n]{0,200}[”]", "", text)
    # Drop quoted reply / blockquote lines.
    text = re.sub(r"(?m)^\s*>.*$", "", text)
    return text


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

    scrubbed = strip_safe_zones(last_text)
    if not DASH_PATTERN.search(scrubbed):
        return 0

    matches = []
    for m in DASH_PATTERN.finditer(scrubbed):
        left = max(0, m.start() - 25)
        right = min(len(scrubbed), m.end() + 25)
        matches.append(scrubbed[left:right].strip())

    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "em_dash",
                "matches": matches,
                "snippet": last_text[-400:],
            }) + "\n")
    except Exception:
        pass

    sys.stderr.write(
        "[cc-friction] em/en-dash detected: "
        + ", ".join(repr(m) for m in matches) + "\n"
    )
    sys.stderr.flush()

    snippets = "; ".join(repr(m) for m in matches[:5])
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Em-dash or en-dash detected: " + snippets + ". "
            "Per marshall's house style: never use em-dashes or en-dashes. "
            "Use a hyphen (-), a comma, a colon, or split the sentence. "
            "Revise the output with no em-dash or en-dash characters."
            + PATCH_ONLY
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
