#!/usr/bin/env python3
"""Stop hook: detect 'should I put on a branch?' / 'spawn worktree?' patterns.

Marshall rule: ALWAYS worktrees, no exceptions. If model is about to do
non-trivial feature work and asks whether to branch/worktree, that's friction
because the answer is always YES, NEW WORKTREE.

Hand-validation 2026-04-28 surfaced this as a strong signal across sessions.

Triggers when last assistant text contains a branching question without
'worktree' nearby. Logs to ~/.claude/cc-friction-log.jsonl.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

# Phrases that propose branching/spiking (work-doing actions)
BRANCH_PHRASES = [
    re.compile(r"\bwant me to\b.*\b(spike|put.*on a branch|push.*up|patch|implement|wire up)\b", re.I | re.S),
    re.compile(r"\bshould i\b.*\b(spike|branch|patch|implement|push up)\b", re.I | re.S),
    re.compile(r"\bspin a worktree\b.*\?", re.I),  # asking for worktree = also bad
    re.compile(r"\bopen a (?:new )?worktree\b.*\?", re.I),
]

# If text mentions worktree action being taken (not asking), don't fire
ALREADY_DOING = [
    re.compile(r"\bworktree (created|ready|spawned)\b", re.I),
    re.compile(r"\bspawning worktree\b", re.I),
    re.compile(r"\bin (this|the) worktree\b", re.I),
]


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

    if any(p.search(last_text) for p in ALREADY_DOING):
        return 0

    matches = [p.pattern for p in BRANCH_PHRASES if p.search(last_text)]
    if not matches:
        return 0

    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "worktree_discipline",
                "matches": matches,
                "snippet": last_text[-400:],
            }) + "\n")
    except Exception:
        pass

    sys.stderr.write(
        "[cc-friction] worktree discipline: model asked about branching/spiking instead of "
        "auto-spawning a worktree.\n"
        "[cc-friction] CLAUDE.md rule: ALWAYS worktrees for non-trivial work. "
        "Don't ask, just `git worktree add`.\n"
    )
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
