#!/usr/bin/env python3
"""PreToolUse Write/Edit hook: block writes inside a tombstoned directory.

A directory containing a `.killed` file has been deliberately retired (the
tombstone explains why + names the PR that did it). Writing into it almost
always means re-introducing something that was already removed.

Real incident 2026-05-04: PR #433 added `.github/workflows/ci.yml` back
even though PR #419 (PTV cut 9/N) had killed GHA in favor of Dockerfile +
Railway pre-deploy. Nothing in the session surfaced #419.

This hook walks parent dirs of the target path. If any contains `.killed`,
the tool call is blocked and the tombstone contents are shown so the actor
sees the kill rationale before deciding whether to override.

Override: delete the `.killed` file in a separate, intentional commit that
explicitly resurrects the surface. That commit is the audit trail.
Emergency bypass: set CLAUDE_KILLED_BYPASS=1 in env for one command.

Tombstone format (free text, conventional fields):

    Killed in PR #<n> (<date>).
    Reason: <one-line why>.
    Resurrect by: <criteria, or "do not resurrect">.
"""
import json
import os
import sys


TOMBSTONE = ".killed"


def find_tombstone(path: str) -> str | None:
    """Walk up from path's parent dir looking for a .killed file. Stop at
    repo root (.git) or filesystem root."""
    if not path:
        return None
    cur = os.path.dirname(os.path.abspath(path))
    while cur and cur != "/":
        candidate = os.path.join(cur, TOMBSTONE)
        if os.path.isfile(candidate):
            return candidate
        # Stop at repo root so we don't escape the repo.
        if os.path.isdir(os.path.join(cur, ".git")):
            return None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    return None


def main():
    if os.environ.get("CLAUDE_KILLED_BYPASS") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") not in ("Write", "Edit", "NotebookEdit"):
        return 0

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    tomb = find_tombstone(file_path)
    if not tomb:
        return 0

    # Allow editing the tombstone itself (intentional revival or update).
    if os.path.abspath(file_path) == os.path.abspath(tomb):
        return 0

    try:
        with open(tomb, "r") as f:
            contents = f.read().strip()
    except Exception:
        contents = "(could not read tombstone)"

    rel_tomb = os.path.relpath(tomb)
    rel_target = os.path.relpath(file_path)

    reason = (
        f"Blocked: writing to `{rel_target}` but `{rel_tomb}` marks this "
        f"directory as deliberately retired.\n\n"
        f"--- {rel_tomb} ---\n{contents}\n--- end tombstone ---\n\n"
        f"Read the tombstone before proceeding. If resurrection is genuinely "
        f"correct, delete the tombstone in a separate commit that explains "
        f"why -- that commit is the audit trail.\n\n"
        f"Emergency bypass: set CLAUDE_KILLED_BYPASS=1 for one command."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
