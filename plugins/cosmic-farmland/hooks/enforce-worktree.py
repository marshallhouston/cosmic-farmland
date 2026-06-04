#!/usr/bin/env python3
"""PreToolUse Bash hook: block branch creation from primary worktree.

Marshall rule (CLAUDE.md): ALWAYS worktrees, no exceptions for non-trivial work.
Passive measurement (worktree-discipline.py logs asking patterns) is not enough --
the model can silently `git checkout -b` from the primary checkout, commit, push,
and ship without ever asking, bypassing the rule entirely. Real incident
2026-05-03: PR #429 created this way despite worktree-discipline.py being live.

This hook fires on Bash before the command runs. If the command creates a new
branch and cwd is the primary worktree (not a linked worktree), block and tell
the model to use `git worktree add` instead.

Detection of primary vs linked worktree: in a linked worktree, `git rev-parse
--git-dir` returns a path under .git/worktrees/<name>; in the primary, it
returns the .git dir directly. Equivalent: `--git-common-dir` == `--git-dir`
means primary.

Bypass: set CLAUDE_WORKTREE_BYPASS=1 in env (rare, e.g. fixing main directly).
"""
import json
import os
import re
import shlex
import subprocess
import sys


# Branch-creation patterns. Conservative: only flags that DEFINITELY create a branch.
BRANCH_CREATE = [
    re.compile(r"\bgit\s+checkout\s+-b\b"),
    re.compile(r"\bgit\s+switch\s+-c\b"),
    re.compile(r"\bgit\s+switch\s+--create\b"),
    re.compile(r"\bgit\s+branch\s+(?!-[dDvla]|--list|--show|--delete|--move)[A-Za-z0-9_/.-]+\s+"),
]


def is_primary_worktree(cwd: str) -> bool:
    """Return True if cwd is the primary worktree (not a linked worktree)."""
    try:
        common = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        gitdir = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--git-dir"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return os.path.realpath(common) == os.path.realpath(gitdir)
    except Exception:
        return False


def dirty_files(cwd: str):
    """Return list of uncommitted (tracked-modified + untracked) paths, or []."""
    try:
        out = subprocess.check_output(
            ["git", "-C", cwd, "status", "--porcelain"],
            stderr=subprocess.DEVNULL, text=True,
        )
        return [ln[3:].strip() for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def main():
    if os.environ.get("CLAUDE_WORKTREE_BYPASS") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    cmd = payload.get("tool_input", {}).get("command", "")
    if not cmd:
        return 0

    if not any(p.search(cmd) for p in BRANCH_CREATE):
        return 0

    # cwd: tool may run in arbitrary dir; default to session cwd
    cwd = payload.get("cwd") or os.getcwd()

    if not is_primary_worktree(cwd):
        return 0

    # Suggest worktree path: sibling dir of primary, branch-name-derived
    branch_match = re.search(
        r"git\s+(?:checkout\s+-b|switch\s+(?:-c|--create)|branch)\s+(\S+)",
        cmd,
    )
    branch = branch_match.group(1) if branch_match else "<branch>"
    repo_name = os.path.basename(cwd.rstrip("/"))
    parent = os.path.dirname(cwd.rstrip("/"))
    slug = branch.replace("/", "-")
    suggested_path = os.path.join(parent, f"{repo_name}-{slug}")

    dirty = dirty_files(cwd)
    header = (
        f"Blocked: branch creation from primary worktree ({cwd}).\n"
        f"Marshall rule: ALWAYS worktrees, no exceptions. Branching in the primary "
        f"checkout pollutes main + skips the isolation discipline.\n\n"
    )
    bypass = (
        f"\nBypass (rare, e.g. literal hotfix on main): "
        f"set CLAUDE_WORKTREE_BYPASS=1 for one command."
    )

    if dirty:
        # Primary has uncommitted edits. A bare `worktree add` from main would
        # leave them behind. Carry them across via a global stash (stash is
        # shared across worktrees of the same repo, so pop works in the new one).
        listed = "\n".join(f"    {fn}" for fn in dirty[:12])
        more = f"\n    ... (+{len(dirty) - 12} more)" if len(dirty) > 12 else ""
        reason = (
            header
            + f"Primary has uncommitted changes:\n{listed}{more}\n\n"
            + "Carry them into a fresh managed worktree -- run verbatim:\n"
            + "  1) git -C " + cwd + " stash push -u -m _wt_carry\n"
            + f"  2) EnterWorktree name={slug}\n"
            + "  3) git stash pop   (cwd is now the worktree; the stash is "
            + "shared across worktrees of the same repo)\n"
            + "Then commit + push from the worktree as usual.\n"
            + "Do NOT `git worktree add` an external path -- EnterWorktree only "
            + "manages .claude/worktrees/ and Write/Edit are path-guarded to cwd."
            + bypass
        )
    else:
        reason = (
            header
            + "Use instead (managed worktree -- Write/Edit work immediately):\n"
            + f"  EnterWorktree name={slug}\n"
            + "This creates .claude/worktrees/" + slug + " on a fresh branch from "
            + "origin/<default> and switches the session into it.\n"
            + "Do NOT `git worktree add` an external path (e.g. "
            + f"{suggested_path}): EnterWorktree only manages worktrees under "
            + ".claude/worktrees/ and rejects external paths, and Write/Edit are "
            + "path-guarded to the session cwd -- so the external route dead-ends."
            + bypass
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
