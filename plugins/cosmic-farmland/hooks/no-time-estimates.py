#!/usr/bin/env python3
"""Stop hook: detect time-duration estimates in last assistant message.

Per marshall's CLAUDE.md "Marshall voice + product discipline rules":
  No time estimates. Never estimate duration in days/weeks. Describe
  scope, complexity, and decomposition options instead.

Calibration: model drifts toward "this takes 10 min" / "2-4 weeks" framing
even when the rule is in the system prompt. Hook closes the loop post-hoc.

Inputs (stdin JSON from CC):
  - transcript_path: ~/.claude/projects/.../<sid>.jsonl
  - session_id, hook_event_name, etc.

Outputs:
  - stderr: warning to marshall's terminal
  - JSON {decision: block, reason: ...} on stdout: blocks Stop, forces model
    to revise output in-turn with corrective feedback.
  - Append to ~/.claude/cc-friction-log.jsonl for later analysis
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
    the assistant write is still pending. Poll briefly, then read.
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


# Time-duration unit patterns. Matches "10 min", "2-4 weeks", "1.5 hours", etc.
# Requires a digit immediately before the unit (with optional whitespace,
# range hyphen, or decimal). Word-boundary at both ends.
TIME_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*"
    r"(?:s|sec|secs|second|seconds|"
    r"min|mins|minute|minutes|"
    r"hr|hrs|hour|hours|"
    r"day|days|"
    r"week|weeks|"
    r"month|months|"
    r"yr|yrs|year|years)\b",
    re.IGNORECASE,
)

# Header tokens that mark a markdown table as DATA (telemetry, metrics, specs)
# rather than a forward-looking estimate table. If a table's header row contains
# any of these, every cell is a measured value -- drop the whole table before
# linting (mirrors the quoted-span / code-span citation rule). Without this,
# per-cell durations like "12720ms" never see the "P95" column header (it's rows
# away, outside the +-40 char context window) and false-fire.
_TABLE_DATA_HEADER = re.compile(
    r"\b(p001|p01|p05|p10|p25|p50|p75|p90|p95|p99|p999|"
    r"max|min|avg|mean|median|runs?|count|duration|latency|"
    r"ms|sec|seconds?|elapsed|boot|p\d{2,3})\b",
    re.IGNORECASE,
)


def _strip_data_tables(text: str) -> str:
    """Drop markdown tables whose header row marks them as data."""
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Table block: "|...|" header, "|---|" separator, then "|...|" rows.
        if line.lstrip().startswith("|") and i + 1 < n and re.match(
            r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1]
        ):
            header_is_data = bool(_TABLE_DATA_HEADER.search(line))
            j = i + 2
            while j < n and lines[j].lstrip().startswith("|"):
                j += 1
            if header_is_data:
                i = j  # skip the whole table
                continue
            out.extend(lines[i:j])
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


# Lines we should NOT lint. Strip these before applying the pattern.
def strip_safe_zones(text: str) -> str:
    # Drop fenced code blocks.
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Drop data tables (telemetry/metrics) -- cells are measured values.
    text = _strip_data_tables(text)
    # Drop inline code spans.
    text = re.sub(r"`[^`\n]*`", "", text)
    # Drop quoted spans (straight + curly double quotes). Quoting is citation --
    # UI copy ("4 plans, 3-16 days each"), a measured value ("ran in 70s"), or a
    # spec excerpt -- not a forward-looking estimate. Mirrors the code-span rule.
    text = re.sub(r"\"[^\"\n]{0,120}\"", "", text)
    text = re.sub(r"[“][^“”\n]{0,120}[”]", "", text)
    # Drop quoted reply / blockquote lines.
    text = re.sub(r"(?m)^\s*>.*$", "", text)
    return text


# Lexical exceptions: phrases where a digit+unit is referring to data, not an
# estimate. These are checked against the matched substring's local context.
CONTEXT_WHITELIST = [
    "ago",            # "2 weeks ago" = historical reference
    "version",        # "v2 weeks" style copy
    "verify",         # "Re-verify quarterly" mentions etc.
    "trailing",       # "trailing 7 days" in dashboards
    "last verified",  # "last verified 7 days ago"
    "p50", "p95", "p99",  # "P95 200 ms" is data, not an estimate
    "ms",             # already handled but be explicit
    "elapsed",        # "elapsed 256 ms"
    "interval",       # SQL "INTERVAL 7 DAY"
    "window",         # "7d window"
    # Measurements of something that already happened -- not a prediction.
    # Keep these DIRECTIONAL (verb/preposition), not bare nouns: bare "build"
    # would also whitelist the forward estimate "3 days to build".
    "took",           # "the build took 3 min"
    "ran in",         # "ran in 70s"
    "ran for",
    "completed in",
    "finished in",
    "deployed in",    # "deployed in 70s"
    "deploy in",      # "deploy in 70s"
    "booted in",      # "booted in 4s"
    # Code / config constants referenced by value, not estimated.
    "dwell",          # "20s dwell gate" -- READ_DWELL_MS constant
    "timeout",        # "30s timeout"
    "constant",       # "the 20s constant"
    "_ms",            # "READ_DWELL_MS = 20s"
]


def is_data_context(text: str, match_start: int, match_end: int) -> bool:
    """Check ~40 chars around match for data-context whitelist phrases."""
    left = max(0, match_start - 40)
    right = min(len(text), match_end + 20)
    window = text[left:right].lower()
    return any(kw in window for kw in CONTEXT_WHITELIST)


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
    for m in TIME_PATTERN.finditer(scrubbed):
        if is_data_context(scrubbed, m.start(), m.end()):
            continue
        matches.append(m.group(0))

    if not matches:
        return 0

    # log violation
    log_path = os.path.expanduser("~/.claude/cc-friction-log.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": payload.get("session_id"),
                "type": "time_estimate",
                "matches": matches,
                "snippet": last_text[-400:],
            }) + "\n")
    except Exception:
        pass

    sys.stderr.write(
        f"[cc-friction] time-estimate detected: {', '.join(repr(m) for m in matches)}\n"
    )
    sys.stderr.flush()

    matched_phrases = ", ".join(repr(m) for m in matches)
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Time-duration estimate detected: {matched_phrases}. "
            "Per CLAUDE.md 'Marshall voice + product discipline rules': "
            "no time estimates. Never estimate duration in seconds/minutes/hours/days/weeks/months. "
            "Describe scope, complexity, and decomposition options instead "
            "(e.g. 'Low complexity: single edit + test' rather than '5 minutes'). "
            "Revise the output without numeric time units."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
