#!/usr/bin/env python3
"""Contract tests for cosmic-farmland Claude Code hooks.

These hooks gate EVERY turn (Stop) or EVERY matching tool call (PreToolUse).
A false-positive in a Stop hook silently blocks the model's turn; a regex that
stops matching silently lets drift through. Neither failure is visible until a
session feels wrong. This suite locks the contract:

  - Stop hooks      : stdin {transcript_path} -> read last assistant text ->
                      maybe print {"decision":"block",...}. Always exit 0.
  - PreToolUse hooks: stdin {tool_name, tool_input, cwd} ->
                      maybe print {"hookSpecificOutput":{permissionDecision:"deny"}}.

Each hook runs as a real subprocess with crafted stdin, exactly as Claude Code
invokes it. HOME is redirected to a temp dir so the friction log doesn't leak
into the real ~/.claude.

Stdlib only (unittest) so it runs anywhere with bare python3, no pip install.

Run: python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "plugins" / "cosmic-farmland" / "hooks"


def clean_env(**overrides):
    """os.environ minus all GIT_* vars, plus any overrides.

    When this suite runs from the pre-push hook, git exports GIT_DIR /
    GIT_INDEX_FILE / GIT_WORK_TREE into the hook subprocess. Those leak into
    the temp-repo `git init`/`add`/`commit` calls in TestEnforceWorktree.setUp
    and make them operate on the REAL repo (corrupting it; the suite errors).
    Standalone the vars are absent, so the failure only shows under pre-push.
    Strip every GIT_* var for any git subprocess this suite spawns.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(overrides)
    return env


# --- harness ---------------------------------------------------------------

def run_hook(name, payload, home, cwd=None, env_extra=None):
    """Run a hook as a subprocess with `payload` on stdin. Returns (rc, parsed_stdout).

    parsed_stdout is the JSON object the hook printed, or None if it printed
    nothing (raw string if it printed non-JSON, to make failures legible).
    """
    env = clean_env()
    env["HOME"] = str(home)            # redirect ~/.claude/cc-friction-log.jsonl
    env.pop("CLAUDE_WORKTREE_BYPASS", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env, cwd=cwd, timeout=10,
    )
    out = proc.stdout.strip()
    parsed = None
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = out
    return proc.returncode, parsed


def make_transcript(home, assistant_text):
    """Write a minimal CC transcript whose last record is an assistant turn."""
    rec = {"type": "assistant", "message": {"content": [
        {"type": "text", "text": assistant_text},
    ]}}
    p = Path(home) / "transcript.jsonl"
    p.write_text(
        json.dumps({"type": "user", "message": {"content": "go"}}) + "\n"
        + json.dumps(rec) + "\n"
    )
    return str(p)


def stop_payload(home, text):
    return {"transcript_path": make_transcript(home, text),
            "session_id": "test", "hook_event_name": "Stop"}


def is_block(parsed):
    return isinstance(parsed, dict) and parsed.get("decision") == "block"


def is_deny(parsed):
    return (isinstance(parsed, dict)
            and parsed.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")


class HookTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        (self.home / ".claude").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()


# --- no-reasking.py (Stop) -------------------------------------------------

class TestReasking(HookTestCase):
    def test_blocks(self):
        for text in ["Want me to ship #1?", "Should I run the tests?",
                     "Would you like me to refactor this?", "thoughts?"]:
            with self.subTest(text=text):
                rc, out = run_hook("no-reasking.py", stop_payload(self.home, text), self.home)
                self.assertEqual(rc, 0)
                self.assertTrue(is_block(out), f"expected block for {text!r}, got {out!r}")

    def test_allows(self):
        for text in [
            "Shipped the PR. Build is green.",                  # statement, no question
            "Want me to delete the stale branch?",              # destructive -> allowed
            "Should I force push to overwrite the remote?",     # destructive -> allowed
            "This will drop table users. Want me to proceed?",  # drop table -> allowed
        ]:
            with self.subTest(text=text):
                rc, out = run_hook("no-reasking.py", stop_payload(self.home, text), self.home)
                self.assertEqual(rc, 0)
                self.assertFalse(is_block(out), f"expected no block for {text!r}, got {out!r}")


# --- no-time-estimates.py (Stop) -------------------------------------------

class TestTimeEstimates(HookTestCase):
    def test_blocks(self):
        for text in ["This will take about 10 minutes.", "Roughly 2-4 weeks of work.",
                     "Give it 1.5 hours.", "Should land in 3 days."]:
            with self.subTest(text=text):
                rc, out = run_hook("no-time-estimates.py", stop_payload(self.home, text), self.home)
                self.assertEqual(rc, 0)
                self.assertTrue(is_block(out), f"expected block for {text!r}, got {out!r}")

    def test_allows(self):
        for text in [
            "P95 latency is 200 ms, well within budget.",       # data, not estimate
            "That bug shipped 2 weeks ago.",                    # historical
            "Dashboard shows the trailing 7 days of signups.",  # data context
            "Query uses INTERVAL 7 DAY in the where clause.",   # SQL data
            "Low complexity: one edit plus a test.",            # the desired framing
            "Run `sleep 30 seconds` to reproduce.",             # inline code stripped
            "```\nestimated 5 hours of compute\n```",           # code fence stripped
            "> their PR said 3 weeks",                          # blockquote stripped
        ]:
            with self.subTest(text=text):
                rc, out = run_hook("no-time-estimates.py", stop_payload(self.home, text), self.home)
                self.assertEqual(rc, 0)
                self.assertFalse(is_block(out), f"expected no block for {text!r}, got {out!r}")


# --- no-drift.py (Stop) — warn-only, must never block ----------------------

class TestDrift(HookTestCase):
    def test_matches_but_never_blocks(self):
        for text in ["Let's tackle this next sprint.", "Plan for the sprint:", "1. apply all"]:
            with self.subTest(text=text):
                rc, out = run_hook("no-drift.py", stop_payload(self.home, text), self.home)
                self.assertEqual(rc, 0)
                self.assertFalse(is_block(out))

    def test_clean_text_silent(self):
        rc, out = run_hook("no-drift.py", stop_payload(self.home, "Shipped. Next: wire the API."), self.home)
        self.assertEqual(rc, 0)
        self.assertIsNone(out)


# --- worktree-discipline.py (Stop) — warn-only -----------------------------

class TestWorktreeDiscipline(HookTestCase):
    def test_clean_silent(self):
        rc, out = run_hook("worktree-discipline.py",
                           stop_payload(self.home, "Worktree created. Working there now."), self.home)
        self.assertEqual(rc, 0)
        self.assertIsNone(out)

    def test_match_no_block(self):
        rc, out = run_hook("worktree-discipline.py",
                           stop_payload(self.home, "Should I spike this on a branch?"), self.home)
        self.assertEqual(rc, 0)
        self.assertFalse(is_block(out))


# --- no-asking-tool.py (PreToolUse: AskUserQuestion) — warn-only -----------

class TestAskingTool(HookTestCase):
    def test_ignores_other_tools(self):
        rc, out = run_hook("no-asking-tool.py",
                           {"tool_name": "Bash", "tool_input": {"command": "ls"}}, self.home)
        self.assertEqual(rc, 0)
        self.assertIsNone(out)

    def test_warns_no_deny(self):
        payload = {"tool_name": "AskUserQuestion",
                   "tool_input": {"question": "Which color?",
                                  "options": [{"label": "red"}, {"label": "blue"}]}}
        rc, out = run_hook("no-asking-tool.py", payload, self.home)
        self.assertEqual(rc, 0)
        self.assertFalse(is_deny(out))


# --- enforce-worktree.py (PreToolUse: Bash) --------------------------------

class TestEnforceWorktree(HookTestCase):
    def setUp(self):
        super().setUp()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        env = clean_env(HOME=self._tmp.name)
        for cmd in (["git", "init", "-q", "-b", "main"],
                    ["git", "config", "user.email", "t@t.t"],
                    ["git", "config", "user.name", "t"]):
            subprocess.run(cmd, cwd=self.repo, env=env, check=True)
        (self.repo / "f.txt").write_text("x")
        subprocess.run(["git", "add", "."], cwd=self.repo, env=env, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=self.repo, env=env, check=True)

    def _bash(self, command):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo)}

    def test_denies_branch_from_primary(self):
        for command in ["git checkout -b feature/x", "git switch -c feature/x",
                        "git switch --create feature/x"]:
            with self.subTest(command=command):
                rc, out = run_hook("enforce-worktree.py", self._bash(command), self.home)
                self.assertEqual(rc, 0)
                self.assertTrue(is_deny(out), f"expected deny for {command!r}, got {out!r}")

    def test_allows_nonbranching(self):
        for command in ["git status", "git checkout main", "git branch -d old", "ls -la"]:
            with self.subTest(command=command):
                rc, out = run_hook("enforce-worktree.py", self._bash(command), self.home)
                self.assertEqual(rc, 0)
                self.assertFalse(is_deny(out), f"expected no deny for {command!r}, got {out!r}")

    def test_bypass_env(self):
        rc, out = run_hook("enforce-worktree.py", self._bash("git checkout -b x"), self.home,
                           env_extra={"CLAUDE_WORKTREE_BYPASS": "1"})
        self.assertEqual(rc, 0)
        self.assertFalse(is_deny(out))

    def test_ignores_non_bash(self):
        rc, out = run_hook("enforce-worktree.py", {"tool_name": "Edit", "tool_input": {}}, self.home)
        self.assertEqual(rc, 0)
        self.assertIsNone(out)


# --- shared contract: malformed / missing input never crashes -------------

ALL_HOOKS = ["no-reasking.py", "no-time-estimates.py", "no-drift.py",
             "worktree-discipline.py", "no-asking-tool.py", "enforce-worktree.py"]
STOP_HOOKS = ["no-reasking.py", "no-time-estimates.py", "no-drift.py", "worktree-discipline.py"]


class TestRobustness(HookTestCase):
    def test_garbage_stdin_exits_zero(self):
        for name in ALL_HOOKS:
            with self.subTest(hook=name):
                env = clean_env(HOME=str(self.home))
                proc = subprocess.run([sys.executable, str(HOOKS / name)],
                                      input="not json at all", capture_output=True,
                                      text=True, env=env, timeout=10)
                self.assertEqual(proc.returncode, 0)

    def test_missing_transcript_exits_zero(self):
        for name in STOP_HOOKS:
            with self.subTest(hook=name):
                rc, out = run_hook(name, {"transcript_path": "/nope/missing.jsonl"}, self.home)
                self.assertEqual(rc, 0)
                self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
