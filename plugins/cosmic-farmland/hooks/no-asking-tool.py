#!/usr/bin/env python3
"""PreToolUse hook: flag AskUserQuestion tool calls as re-asking.

Audit 2026-04-27 showed re-asking can manifest as a tool call (AskUserQuestion),
not just text. Stop hook (no-reasking.py) only inspects text.

This hook fires before AskUserQuestion executes. If the question is about a
destructive op (delete, drop, force push, etc.), allow. Otherwise warn to
stderr + log. Non-blocking.
"""
import json
import sys
import os
from datetime import datetime, timezone

SAFE_CONTEXT = [
    "delete", "drop table", "force push", "rm -rf", "reset --hard",
    "destructive", "irreversible", "uninstall", "revoke", "overwrite",
]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "AskUserQuestion":
        return 0

    tool_input = payload.get("tool_input", {})
    question = tool_input.get("question", "") if isinstance(tool_input, dict) else ""
    options = ""
    if isinstance(tool_input, dict):
        opts = tool_input.get("options", []) or []
        if isinstance(opts, list):
            options = " ".join(o.get("label", "") if isinstance(o, dict) else str(o) for o in opts)
    blob = (question + " " + options).lower()

    if any(kw in blob for kw in SAFE_CONTEXT):
        return 0

    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "ask_user_question_tool",
                "question": question[:200],
            }) + "\n")
    except Exception:
        pass

    sys.stderr.write(
        f"[cc-friction] AskUserQuestion fired w/o destructive context.\n"
        f"[cc-friction] question: {question[:120]!r}\n"
        f"[cc-friction] CLAUDE.md output discipline #4: act on obvious next step instead.\n"
    )
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
