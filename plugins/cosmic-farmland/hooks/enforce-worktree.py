#!/usr/bin/env python3
"""PreToolUse Bash hook: block branch creation from primary worktree.

Marshall rule (CLAUDE.md): ALWAYS worktrees, no exceptions for non-trivial work.
Passive measurement (worktree-discipline.py logs asking patterns) is not enough --
the model can silently create a branch (`checkout -b` / `switch -c`) from the
primary checkout, commit, push, and ship without ever asking, bypassing the rule
entirely. Real incident 2026-05-03: PR #429 created this way despite
worktree-discipline.py being live.

This hook fires on Bash before the command runs. If the command creates a new
branch and the *target* repo is a primary worktree (not a linked worktree),
block and point at the right remedy.

Target resolution: the tool reports the session launch dir as cwd, but a single
command can retarget another repo via a leading `cd <dir> &&` or `git -C <dir>`.
`effective_cwd` honors those so a cross-repo tooling edit is judged against the
repo it actually touches, not the session repo. When the target differs from the
session repo, EnterWorktree (which only manages the session repo's worktrees)
can't help, so the remedy switches to a plain `git worktree add` in the target.
(why: 2026-06-10 false-positive -- `cd /other/repo && <branch-create>` blocked
with an unusable EnterWorktree suggestion + the session repo's dirty files.)

Detection of primary vs linked worktree: in a linked worktree, `git rev-parse
--git-dir` returns a path under .git/worktrees/<name>; in the primary, it
returns the .git dir directly. Equivalent: `--git-common-dir` == `--git-dir`
means primary.

Bypass: set CLAUDE_WORKTREE_BYPASS=1 in env (rare, e.g. fixing main directly).
"""
import json
import os
import re
import subprocess
import sys


# Optional `-C <dir>` (and similar) between `git` and the subcommand, so the
# branch-create patterns and effective_cwd both see the `git -C <dir> ...` form.
_PRE = r"(?:-C\s+\S+\s+)?"

# Branch-creation patterns. Conservative: only flags that DEFINITELY create a
# branch. Anchored at segment start (^) -- matched against individual shell
# segments whose head is the git invocation, NOT searched across the whole
# command string. That distinction is load-bearing: a command that merely
# QUOTES the pattern (an echoed string, a commit message, a JSON/test payload)
# must NOT trip the guard -- only an actually-executed branch create should.
# (why: 2026-06-10 -- the old `\bgit...` *search* fired on any command that
# contained the literal substring anywhere, e.g. a hook-test harness feeding a
# crafted payload or `echo`/`printf` of the pattern, blocking benign Bash.)
BRANCH_CREATE = [
    re.compile(r"^git\s+" + _PRE + r"checkout\s+-b\b"),
    re.compile(r"^git\s+" + _PRE + r"switch\s+-c\b"),
    re.compile(r"^git\s+" + _PRE + r"switch\s+--create\b"),
    re.compile(r"^git\s+" + _PRE + r"branch\s+(?!-[dDvla]|--list|--show|--delete|--move)[A-Za-z0-9_/.-]+\s+"),
]

# Leading `VAR=val ` env-assignment prefixes on a simple command (e.g.
# `FOO=1 git ...`). Stripped before head-matching so they can't hide a real
# branch create behind an assignment.
_ASSIGN = re.compile(r"^(?:\w+=(?:'[^']*'|\"[^\"]*\"|\S+)\s+)*")


def _segments(cmd: str):
    """Split a command line into shell segments on && || ; | and newlines.

    Each segment is one simple-command candidate. A `cd /r && <branch-create>`
    line splits so the create is judged as a segment head, not as a substring of
    the whole line.
    """
    return re.split(r"&&|\|\||[;\n|]", cmd)


def flags_branch_create(cmd: str) -> bool:
    """True iff some shell segment's HEAD is an actual branch-create git command.

    Substring mentions inside echo/printf/commit-message/quoted args do not
    count -- their segment head is `echo`/`printf`/`git commit`/etc., not a
    branch-create `git`.
    """
    for seg in _segments(cmd):
        seg = _ASSIGN.sub("", seg.strip())
        if any(p.match(seg) for p in BRANCH_CREATE):
            return True
    return False


def effective_cwd(cmd: str, session_cwd: str) -> str:
    """Resolve the dir the git command actually targets.

    A `git -C <dir>` on the command wins (it is what git itself uses); else a
    leading `cd <dir> &&|;` prefix. Relative paths resolve against session_cwd.
    Falls back to session_cwd when nothing resolves to a real directory.
    """
    cand = None
    c_flags = re.findall(r"\bgit\s+-C\s+(['\"]?)([^'\"\s]+)\1", cmd)
    if c_flags:
        cand = c_flags[-1][1]
    else:
        cd = re.match(r"\s*cd\s+(['\"]?)([^'\"&;|]+)\1\s*(?:&&|;)", cmd)
        if cd:
            cand = cd.group(2).strip()
    if not cand:
        return session_cwd
    cand = os.path.expanduser(cand)
    if not os.path.isabs(cand):
        cand = os.path.join(session_cwd, cand)
    return cand if os.path.isdir(cand) else session_cwd


def repo_root(cwd: str):
    try:
        return os.path.realpath(subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip())
    except Exception:
        return None


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

    if not flags_branch_create(cmd):
        return 0

    session_cwd = payload.get("cwd") or os.getcwd()
    cwd = effective_cwd(cmd, session_cwd)

    if not is_primary_worktree(cwd):
        return 0

    cross_repo = repo_root(cwd) != repo_root(session_cwd)

    # Suggest worktree path: sibling dir of the TARGET primary, branch-derived
    branch_match = re.search(
        r"git\s+" + _PRE + r"(?:checkout\s+-b|switch\s+(?:-c|--create)|branch)\s+(\S+)",
        cmd,
    )
    branch = branch_match.group(1) if branch_match else "<branch>"
    repo_name = os.path.basename(cwd.rstrip("/"))
    parent = os.path.dirname(cwd.rstrip("/"))
    slug = branch.replace("/", "-")
    suggested_path = os.path.join(parent, f"{repo_name}-{slug}")

    header = (
        f"Blocked: branch creation from primary worktree ({cwd}).\n"
        f"Marshall rule: ALWAYS worktrees, no exceptions. Branching in the primary "
        f"checkout pollutes main + skips the isolation discipline.\n\n"
    )
    bypass = (
        f"\nBypass (rare, e.g. literal hotfix on main): "
        f"set CLAUDE_WORKTREE_BYPASS=1 for one command."
    )

    if cross_repo:
        # Target is a different repo than the session. EnterWorktree only
        # manages the session repo's worktrees, so it can't help here -- use a
        # plain git worktree in the target repo instead.
        reason = (
            header
            + f"This command targets a different repo ({cwd}) than the session "
            + f"({session_cwd}).\n"
            + "EnterWorktree only manages the session repo, so make a plain "
            + "worktree in the target:\n"
            + f"  git -C {cwd} worktree add {suggested_path} -b {branch}\n"
            + f"  cd {suggested_path}   # then commit + push from there\n"
            + bypass
        )
    elif dirty_files(cwd):
        # Primary has uncommitted edits. A bare `worktree add` from main would
        # leave them behind. Carry them across via a global stash (stash is
        # shared across worktrees of the same repo, so pop works in the new one).
        dirty = dirty_files(cwd)
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
