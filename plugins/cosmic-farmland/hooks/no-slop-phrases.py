#!/usr/bin/env python3
"""Stop hook: detect inflated "AI slop" phrasing in the last assistant message.

Per marshall's house style: value simplicity and directness. The model reaches
for inflated connectives ("the cost is stark", "the numbers are blunt", "moved
the needle") that add emphasis without adding information. They read as machine
prose and marshall's verdict on them was "it's gross".

Calibration: caught in the Meadow Hills scouting report (2026-09-15), which
carried eleven of these in one document plus "actually" five times and the
"X is Y. Z is not." antithesis four times.

The blocklist is deliberately CONSERVATIVE. Every entry is a phrase that is
essentially never the right call, so a match is a near-certain violation.
Judgment-requiring cadence (the antithesis pattern, chiasmus, general
over-writing) is NOT mechanizable and lives in CLAUDE.md instead.

Deliberately absent: "deep dive" (marshall uses it himself), "that being said"
(ordinary speech), and bare "actually" (legitimate in contrast). "actually" is
instead caught on density, not presence.

ponytail: gates chat prose only, like its three sibling voice hooks. Prose
written INTO a file (the actual Meadow Hills case) goes through Write/Edit/Bash
and is never seen here. Upgrade path is a PreToolUse content linter, which needs
heredoc parsing and safe-zoning for code, so it is not worth it until file prose
slips twice more.

Inputs (stdin JSON from CC):
  - transcript_path: ~/.claude/projects/.../<sid>.jsonl

Outputs:
  - stderr: warning to marshall's terminal
  - JSON {decision: block, reason: ...} on stdout: blocks Stop, forces the model
    to revise output in-turn with corrective feedback.
  - Append to ~/.claude/cc-friction-log.jsonl for later analysis

Safe zones (NOT linted): fenced code blocks, inline code spans, quoted spans,
and blockquote lines. Quoting is citation, not authoring, so naming a slop
phrase in order to report cutting it does not trip the hook.
"""
import json
import re
import sys
import os
from datetime import datetime, timezone

from _transcript import PATCH_ONLY, read_last_assistant_text


# Each entry is a phrase that is essentially never the right call. Keep this
# list conservative: a false positive costs marshall a full re-output.
SLOP = [
    r"it(?:'s| is) worth noting",
    r"it(?:'s| is) important to note",
    r"it bears mentioning",
    r"the cost is stark",
    r"the numbers are (?:blunt|stark)",
    r"the honest part",
    r"move[sd]? the needle",
    r"the wheels (?:come|came) off",
    r"highest[- ]leverage",
    r"the single (?:biggest|most)",
    r"speaks volumes",
    r"(?:a|is) testament to",
    r"paradigm shift",
    r"game[- ]changer",
    r"at the end of the day",
    r"needless to say",
    r"delv(?:e|ing) into",
    r"(?:rich )?tapestry of",
    r"under(?:scores|scoring) the",
    r"nothing short of",
    r"serves as a reminder",
]
SLOP_PATTERN = re.compile("|".join("(?:%s)" % p for p in SLOP), re.IGNORECASE)

# "actually" is fine in contrast ("not X but actually Y") and slop in bulk.
HEDGE = re.compile(r"\bactually\b", re.IGNORECASE)
HEDGE_LIMIT = 2


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

    matches = []
    for m in SLOP_PATTERN.finditer(scrubbed):
        left = max(0, m.start() - 25)
        right = min(len(scrubbed), m.end() + 25)
        matches.append(scrubbed[left:right].strip())

    hedges = len(HEDGE.findall(scrubbed))
    over = hedges > HEDGE_LIMIT

    if not matches and not over:
        return 0

    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "slop_phrase",
                "matches": matches,
                "actually_count": hedges,
                "snippet": last_text[-400:],
            }) + "\n")
    except Exception:
        pass

    bits = []
    if matches:
        bits.append("slop phrasing: " + ", ".join(repr(m) for m in matches[:5]))
    if over:
        bits.append('"actually" used %d times (limit %d)' % (hedges, HEDGE_LIMIT))
    summary = "; ".join(bits)

    sys.stderr.write("[cc-friction] " + summary + "\n")
    sys.stderr.flush()

    print(json.dumps({
        "decision": "block",
        "reason": (
            "Inflated phrasing detected: " + summary + ". "
            "Per marshall's house style: value simplicity and directness. "
            "These add emphasis without adding information. Cut the phrase and "
            "state the thing plainly, or delete the sentence. Do not swap in "
            "another intensifier. Revise the output."
            + PATCH_ONLY
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
