#!/usr/bin/env python3
"""PreToolUse(Skill) hook: emit an un-redacted skill-invocation event to Honeycomb.

Claude Code's native `skill_activated` event redacts locally-sourced skill names
(userSettings / projectSettings / local plugin-dir) to the literal "custom_skill",
and there is no tool_use_id to join a real name back onto it. This hook sees the
real skill name in tool_input before the call runs and posts its own event
(event.name = skill.invoked) carrying the real name + project + best-effort trigger.

Never blocks: always exits 0, posts in the background, swallows all errors. A
telemetry hook must never be able to stop a skill from running.
"""
import json
import os
import re
import subprocess
import sys


def derive_project(cwd: str) -> str:
    """Match the `cc()` wrapper: project = parent dir of the git common-dir, so
    worktrees fold to their main repo. Fall back to the cwd basename."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=cwd, capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if common:
            proj = os.path.basename(os.path.dirname(common))
            if proj and proj not in (".", "/"):
                return proj
    except Exception:
        pass
    return os.path.basename(cwd.rstrip("/")) or "unknown"


def last_user_text(transcript_path: str) -> str:
    """Return the text of the most recent user-role message in the transcript."""
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "user" and rec.get("role") != "user":
                continue
            msg = rec.get("message", rec)
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict)
                )
            return str(content)
    except Exception:
        pass
    return ""


def infer_trigger(skill_name: str, transcript_path: str) -> str:
    """Best-effort. user-slash if the latest user turn invoked this skill by
    slash; otherwise model (proactive or nested — not separable from a hook)."""
    text = last_user_text(transcript_path).strip()
    if not text:
        return "model"
    # Slash form may appear bare ("/ship ...") or wrapped by the CLI in a
    # <command-name>/ship</command-name> block. Match the skill's short name
    # (drop any "plugin:" namespace prefix).
    short = skill_name.split(":")[-1]
    if re.search(r"(^|<command-name>)\s*/" + re.escape(short) + r"\b", text):
        return "user-slash"
    if re.search(r"(^|<command-name>)\s*/" + re.escape(skill_name) + r"\b", text):
        return "user-slash"
    return "model"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Skill":
        return
    tool_input = data.get("tool_input", {}) or {}
    skill_name = tool_input.get("skill") or tool_input.get("name")
    if not skill_name:
        return

    cwd = data.get("cwd") or os.getcwd()
    transcript = data.get("transcript_path", "")

    headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    m = re.search(r"x-honeycomb-team=([^,]+)", headers)
    if not m:
        return  # no key in env; nothing to post to
    api_key = m.group(1).strip()

    payload = {
        "event.name": "skill.invoked",
        "service.name": "claude-code",
        "skill.name": skill_name,
        "skill.namespaced": ":" in skill_name,
        "project": derive_project(cwd),
        "invocation_trigger": infer_trigger(skill_name, transcript),
        "trigger.source": "hook",  # mark provenance: this is our event, not CC's
        "session.id": data.get("session_id", ""),
    }

    # Fire-and-forget. Detached background curl with a hard timeout so a slow
    # network never delays the skill. stdout/err discarded.
    try:
        subprocess.Popen(
            [
                "curl", "-sS", "-m", "5", "-X", "POST",
                "https://api.honeycomb.io/1/events/claude-code",
                "-H", f"X-Honeycomb-Team: {api_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
