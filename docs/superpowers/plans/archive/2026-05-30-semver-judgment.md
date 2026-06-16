> **ARCHIVED — SHIPPED in PR #28.** All tasks complete. Kept for reference.

# Semver Judgment System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the always-patch pre-commit bump with a deterministic floor (commit-type + diff structure) that picks patch/minor/major correctly, gates it at pre-push, and prints a one-line push summary.

**Architecture:** One stdlib-only Python module `scripts/semver_judge.py` holds all version logic as pure, testable functions (commit-message floor, diff-structure floor, version math). The bash githooks call it: `pre-commit` sets the floor idempotently from the staged diff, `pre-push` recomputes over the full range and blocks if the manifest under-bumped. A `bin/bump` wrapper lets the human apply the exact fix when pre-push blocks. No model — see `docs/plans/semver-judgment.md` for why the `claude -p` reviewer was deferred.

**Tech Stack:** Bash githooks (`core.hooksPath=.githooks`), Python 3 stdlib (`unittest`, `subprocess`, `json`), `jq` (already used), git plumbing.

---

## Contract (from docs/plans/semver-judgment.md §2)

- **message_level** — conventional-commit type across the range: `feat`→minor; `fix`/`perf`/`refactor`/`docs`/`chore`/`test`→patch; `!` or `BREAKING CHANGE:`→major; non-conforming subject→patch (safe floor).
- **diff_level** — structural signal in the plugin diff over invokable identifier paths (`skills/<name>/SKILL.md`, `commands/<file>`, `agents/<file>`): delete/rename of such a path→major; add of such a path→minor; else patch.
- **floor = max(message_level, diff_level)** on the order `patch < minor < major`.
- All version `set` operations are **idempotent and raise-only**: computed from the base (origin/main) version, never lowering a manual over-bump.

## File Structure

- **Create** `scripts/semver_judge.py` — all version logic (pure functions + git wrappers + CLI subcommands `level`, `set`, `check`).
- **Create** `bin/bump` — human wrapper: `bin/bump <level> [plugin]` forces a plugin's manifest to base+level.
- **Create** `tests/test_semver_judge.py` — unittest over the pure functions (no git/subprocess needed).
- **Modify** `.githooks/pre-commit` — replace always-patch with idempotent floor `set` from the staged diff.
- **Modify** `.githooks/pre-push` — call `semver_judge.py check` (supersedes the old differs-only check), print summary.
- **Delete** `scripts/check-plugin-version.sh` — the new `check` is strictly stronger (asserts the *level* is correct, not merely that the version differs).

---

## Task 1: semver_judge.py — pure floor logic + `level` subcommand

**Files:**
- Create: `scripts/semver_judge.py`
- Test: `tests/test_semver_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_semver_judge.py
#!/usr/bin/env python3
"""Unit tests for scripts/semver_judge.py — the deterministic version floor.

Pure functions only: no git, no subprocess. The CLI git wrappers are thin and
exercised by the hook integration steps in the plan, not here.

Run: python3 -m unittest discover -s tests -v
"""
import importlib.util
import unittest
from pathlib import Path

# Load scripts/semver_judge.py as a module (it has no .py-package parent).
_PATH = Path(__file__).resolve().parent.parent / "scripts" / "semver_judge.py"
_spec = importlib.util.spec_from_file_location("semver_judge", _PATH)
sj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sj)


class TestMessageLevel(unittest.TestCase):
    def test_feat_is_minor(self):
        self.assertEqual(sj.message_level(["feat: add skill-stats"]), "minor")

    def test_fix_is_patch(self):
        self.assertEqual(sj.message_level(["fix: correct off-by-one"]), "patch")

    def test_chore_docs_refactor_are_patch(self):
        for msg in ["chore: tidy", "docs: readme", "refactor: split"]:
            self.assertEqual(sj.message_level([msg]), "patch")

    def test_bang_is_major(self):
        self.assertEqual(sj.message_level(["feat!: drop /fart-smell"]), "major")

    def test_breaking_change_footer_is_major(self):
        msg = "feat: rework\n\nBREAKING CHANGE: /foo removed"
        self.assertEqual(sj.message_level([msg]), "major")

    def test_scope_is_parsed(self):
        self.assertEqual(sj.message_level(["feat(skill-stats): x"]), "minor")

    def test_nonconforming_subject_is_patch(self):
        self.assertEqual(sj.message_level(["Merge branch 'main'"]), "patch")

    def test_range_takes_max(self):
        self.assertEqual(
            sj.message_level(["fix: a", "feat: b", "chore: c"]), "minor"
        )

    def test_empty_range_is_patch(self):
        self.assertEqual(sj.message_level([]), "patch")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_semver_judge -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError: module has no attribute 'message_level'` (file doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/semver_judge.py
#!/usr/bin/env python3
"""Compute and apply semantic-version bumps for cosmic-farmland plugins.

floor = max(message_level, diff_level):
  message_level — conventional-commit type across the commit range.
    feat -> minor; fix/perf/refactor/docs/chore/test -> patch;
    '!' or 'BREAKING CHANGE:' -> major; non-conforming subject -> patch.
  diff_level — structural signal in the plugin diff.
    delete/rename of an invokable identifier path -> major;
    add of an invokable identifier path -> minor; else patch.

Contract: docs/plans/semver-judgment.md §2. No model. Stdlib only.
"""
import json
import re
import subprocess
import sys

LEVELS = {"patch": 0, "minor": 1, "major": 2}
_PATCH_TYPES = {"fix", "perf", "refactor", "docs", "chore", "test", "style", "ci", "build"}
_SUBJECT_RE = re.compile(r"^(?P<type>\w+)(?:\([^)]*\))?(?P<bang>!)?:")


def rank(level):
    """Numeric rank; None (no bump) ranks below patch."""
    return LEVELS.get(level, -1)


def max_level(a, b):
    return a if rank(a) >= rank(b) else b


def message_level(messages):
    """Highest level implied by a list of full commit messages."""
    level = "patch"
    for msg in messages:
        if not msg.strip():
            continue
        if "BREAKING CHANGE" in msg:
            return "major"
        subject = msg.splitlines()[0]
        m = _SUBJECT_RE.match(subject)
        if not m:
            this = "patch"
        elif m.group("bang"):
            return "major"
        elif m.group("type") == "feat":
            this = "minor"
        else:
            this = "patch"
        level = max_level(level, this)
    return level
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_semver_judge -v`
Expected: PASS (9 tests in TestMessageLevel).

- [ ] **Step 5: Commit**

```bash
git add scripts/semver_judge.py tests/test_semver_judge.py
git commit -m "feat(semver): commit-message version floor"
```

---

## Task 2: diff_level — structural floor from name-status

**Files:**
- Modify: `scripts/semver_judge.py`
- Test: `tests/test_semver_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_semver_judge.py

class TestDiffLevel(unittest.TestCase):
    P = "cosmic-farmland"

    def status(self, *lines):
        # git diff --name-status lines, tab-separated.
        return list(lines)

    def test_added_skill_is_minor(self):
        lines = self.status("A\tplugins/cosmic-farmland/skills/activity-stats/SKILL.md")
        self.assertEqual(sj.diff_level(lines, self.P), "minor")

    def test_added_command_is_minor(self):
        lines = self.status("A\tplugins/cosmic-farmland/commands/foo.md")
        self.assertEqual(sj.diff_level(lines, self.P), "minor")

    def test_added_agent_is_minor(self):
        lines = self.status("A\tplugins/cosmic-farmland/agents/foo.md")
        self.assertEqual(sj.diff_level(lines, self.P), "minor")

    def test_deleted_skill_is_major(self):
        lines = self.status("D\tplugins/cosmic-farmland/skills/old/SKILL.md")
        self.assertEqual(sj.diff_level(lines, self.P), "major")

    def test_renamed_command_is_major(self):
        lines = self.status(
            "R100\tplugins/cosmic-farmland/commands/old.md\tplugins/cosmic-farmland/commands/new.md"
        )
        self.assertEqual(sj.diff_level(lines, self.P), "major")

    def test_modified_skill_body_is_patch(self):
        lines = self.status("M\tplugins/cosmic-farmland/skills/next/SKILL.md")
        self.assertEqual(sj.diff_level(lines, self.P), "patch")

    def test_modified_hook_is_patch(self):
        lines = self.status("M\tplugins/cosmic-farmland/hooks/no-time-estimates.py")
        self.assertEqual(sj.diff_level(lines, self.P), "patch")

    def test_added_non_identifier_file_is_patch(self):
        # A new helper under scripts/ is not an invokable identifier.
        lines = self.status("A\tplugins/cosmic-farmland/scripts/helper.sh")
        self.assertEqual(sj.diff_level(lines, self.P), "patch")

    def test_other_plugin_ignored(self):
        lines = self.status("D\tplugins/obsidian-weaver/skills/x/SKILL.md")
        self.assertEqual(sj.diff_level(lines, self.P), "patch")

    def test_delete_outranks_add(self):
        lines = self.status(
            "A\tplugins/cosmic-farmland/skills/new/SKILL.md",
            "D\tplugins/cosmic-farmland/skills/old/SKILL.md",
        )
        self.assertEqual(sj.diff_level(lines, self.P), "major")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_semver_judge.TestDiffLevel -v`
Expected: FAIL — `AttributeError: module 'semver_judge' has no attribute 'diff_level'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Append to scripts/semver_judge.py (after message_level)

def _is_identifier_path(path, plugin):
    """True if `path` is an invokable identifier for `plugin`:
    skills/<name>/SKILL.md, commands/<file>, or agents/<file>."""
    prefix = "plugins/%s/" % plugin
    if not path.startswith(prefix):
        return False
    rel = path[len(prefix):]
    if re.fullmatch(r"skills/[^/]+/SKILL\.md", rel):
        return True
    if re.fullmatch(r"commands/[^/]+", rel):
        return True
    if re.fullmatch(r"agents/[^/]+", rel):
        return True
    return False


def diff_level(status_lines, plugin):
    """Structural floor from `git diff --name-status` lines for one plugin.

    Each line: '<status>\\t<path>' or, for renames, '<Rxxx>\\t<old>\\t<new>'.
    delete/rename of an identifier path -> major;
    add of an identifier path -> minor; else patch.
    """
    level = "patch"
    for line in status_lines:
        parts = line.split("\t")
        code = parts[0]
        if code.startswith("R") or code.startswith("C"):
            old, new = parts[1], parts[2]
            if _is_identifier_path(old, plugin) or _is_identifier_path(new, plugin):
                return "major"  # rename/copy of an invokable name
            continue
        if len(parts) < 2:
            continue
        path = parts[1]
        if not _is_identifier_path(path, plugin):
            continue
        if code == "D":
            return "major"
        if code == "A":
            level = max_level(level, "minor")
    return level


def floor_level(messages, status_lines, plugin):
    """The deterministic floor: max(message_level, diff_level)."""
    return max_level(message_level(messages), diff_level(status_lines, plugin))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_semver_judge -v`
Expected: PASS (TestMessageLevel + TestDiffLevel).

- [ ] **Step 5: Commit**

```bash
git add scripts/semver_judge.py tests/test_semver_judge.py
git commit -m "feat(semver): structural diff floor (add=minor, delete/rename=major)"
```

---

## Task 3: version math — apply, infer, format

**Files:**
- Modify: `scripts/semver_judge.py`
- Test: `tests/test_semver_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_semver_judge.py

class TestVersionMath(unittest.TestCase):
    def test_parse_format_roundtrip(self):
        self.assertEqual(sj.format_version(sj.parse_version("1.10.0")), "1.10.0")

    def test_apply_patch(self):
        self.assertEqual(sj.bump_version("1.10.3", "patch"), "1.10.4")

    def test_apply_minor_zeroes_patch(self):
        self.assertEqual(sj.bump_version("1.10.3", "minor"), "1.11.0")

    def test_apply_major_zeroes_minor_patch(self):
        self.assertEqual(sj.bump_version("1.10.3", "major"), "2.0.0")

    def test_infer_patch(self):
        self.assertEqual(sj.infer_level("1.10.0", "1.10.1"), "patch")

    def test_infer_minor(self):
        self.assertEqual(sj.infer_level("1.10.0", "1.11.0"), "minor")

    def test_infer_major(self):
        self.assertEqual(sj.infer_level("1.10.0", "2.0.0"), "major")

    def test_infer_equal_is_none(self):
        self.assertIsNone(sj.infer_level("1.10.0", "1.10.0"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_semver_judge.TestVersionMath -v`
Expected: FAIL — `AttributeError: ... has no attribute 'parse_version'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Append to scripts/semver_judge.py (after floor_level)

def parse_version(s):
    major, minor, patch = (int(x) for x in s.split(".")[:3])
    return (major, minor, patch)


def format_version(v):
    return "%d.%d.%d" % v


def bump_version(version_str, level):
    major, minor, patch = parse_version(version_str)
    if level == "major":
        return format_version((major + 1, 0, 0))
    if level == "minor":
        return format_version((major, minor + 1, 0))
    return format_version((major, minor, patch + 1))


def infer_level(old_str, new_str):
    """Level implied by old->new, or None if unchanged."""
    old, new = parse_version(old_str), parse_version(new_str)
    if new[0] > old[0]:
        return "major"
    if new[1] > old[1]:
        return "minor"
    if new[2] > old[2]:
        return "patch"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_semver_judge -v`
Expected: PASS (all three test classes).

- [ ] **Step 5: Commit**

```bash
git add scripts/semver_judge.py tests/test_semver_judge.py
git commit -m "feat(semver): version math (bump, infer, parse)"
```

---

## Task 4: git wrappers + CLI (`level`, `set`, `check`)

**Files:**
- Modify: `scripts/semver_judge.py`
- Test: manual (git-backed; exercised end-to-end in Task 7)

- [ ] **Step 1: Add the git wrappers and CLI**

Append to `scripts/semver_judge.py`. These are thin I/O shims over the pure functions above.

```python
# Append to scripts/semver_judge.py (after infer_level)

def _git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def _manifest_path(plugin):
    return "plugins/%s/plugin.json" % plugin


def _read_version(plugin):
    with open(_manifest_path(plugin)) as f:
        return json.load(f)["version"]


def _base_version(plugin, base):
    """Version of this plugin's manifest at `base` (e.g. origin/main).
    Returns None when the ref or manifest is absent (new plugin / no base)."""
    try:
        blob = _git("show", "%s:%s" % (base, _manifest_path(plugin)))
        return json.loads(blob)["version"]
    except (subprocess.CalledProcessError, ValueError, KeyError):
        return None


def _commit_messages(base):
    """Full messages for base..HEAD, newest-first, NUL-delimited."""
    out = _git("log", "--format=%B%x00", "%s..HEAD" % base)
    return [m for m in out.split("\0") if m.strip()]


def _status_lines(base, staged):
    """name-status lines for the plugin diff.
    staged=True  -> staged changes (pre-commit, no HEAD commit yet).
    staged=False -> base..HEAD (pre-push, full range)."""
    if staged:
        out = _git("diff", "--cached", "--name-status")
    else:
        out = _git("diff", "--name-status", "%s..HEAD" % base)
    return [ln for ln in out.splitlines() if ln.strip()]


def _touched_plugins(staged):
    """Plugin names with changed files (plugins/<name>/...)."""
    lines = _status_lines("HEAD", staged) if staged else _status_lines("origin/main", False)
    names = set()
    for ln in lines:
        for token in ln.split("\t")[1:]:
            parts = token.split("/")
            if len(parts) >= 2 and parts[0] == "plugins":
                names.add(parts[1])
    return sorted(names)


def _compute_floor(plugin, base, staged):
    messages = [] if staged else _commit_messages(base)
    status = _status_lines(base, staged)
    return floor_level(messages, status, plugin)


def cmd_level(plugin, base, staged):
    print(_compute_floor(plugin, base, staged))
    return 0


def cmd_set(plugin, base, level):
    """Idempotent, raise-only: set manifest to base+level unless already >= that."""
    base_v = _base_version(plugin, base)
    cur_v = _read_version(plugin)
    if base_v is None:
        # No base to anchor to (new plugin): only ensure a non-empty version.
        print("set: %s has no base at %s; leaving %s" % (plugin, base, cur_v))
        return 0
    applied = infer_level(base_v, cur_v)
    if rank(applied) >= rank(level):
        print("set: %s already %s (>= %s); no change" % (plugin, cur_v, level))
        return 0
    target = bump_version(base_v, level)
    path = _manifest_path(plugin)
    with open(path) as f:
        data = json.load(f)
    data["version"] = target
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print("set: %s %s -> %s (%s from %s)" % (plugin, cur_v, target, level, base_v))
    return 0


def _summary_changes(plugin, base):
    """Human bits for the push summary: '+skill foo', '-command bar'."""
    bits = []
    for ln in _status_lines(base, staged=False):
        parts = ln.split("\t")
        code = parts[0]
        path = parts[-1]
        if not _is_identifier_path(path, plugin):
            continue
        rel = path[len("plugins/%s/" % plugin):]
        kind = rel.split("/")[0].rstrip("s")  # skills->skill, commands->command
        name = rel.split("/")[1] if rel.startswith("skills/") else rel.split("/")[1].rsplit(".", 1)[0]
        sign = {"A": "+", "D": "-"}.get(code[0], "~")
        bits.append("%s%s %s" % (sign, kind, name))
    return ", ".join(bits)


def cmd_check(plugin, base):
    """Block (exit 1) if the manifest under-bumped vs the required floor."""
    base_v = _base_version(plugin, base)
    if base_v is None:
        print("check: %s new plugin (no base at %s); skip" % (plugin, base))
        return 0
    cur_v = _read_version(plugin)
    required = _compute_floor(plugin, base, staged=False)
    applied = infer_level(base_v, cur_v)
    if rank(applied) < rank(required):
        target = bump_version(base_v, required)
        sys.stderr.write(
            "FAIL: %s needs %s (%s -> %s) but manifest is %s.\n"
            "      Run: bin/bump %s %s\n"
            % (plugin, required, base_v, target, cur_v, required, plugin)
        )
        return 1
    changes = _summary_changes(plugin, base)
    suffix = ": %s" % changes if changes else ""
    print("%s %s->%s (%s)%s" % (plugin, base_v, cur_v, applied, suffix))
    return 0


def main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="semver_judge")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("level")
    pl.add_argument("--plugin", required=True)
    pl.add_argument("--base", default="origin/main")
    pl.add_argument("--staged", action="store_true")

    ps = sub.add_parser("set")
    ps.add_argument("--plugin", required=True)
    ps.add_argument("--base", default="origin/main")
    ps.add_argument("--level", required=True, choices=list(LEVELS))

    pc = sub.add_parser("check")
    pc.add_argument("--plugin", required=True)
    pc.add_argument("--base", default="origin/main")

    a = p.parse_args(argv)
    if a.cmd == "level":
        return cmd_level(a.plugin, a.base, a.staged)
    if a.cmd == "set":
        return cmd_set(a.plugin, a.base, a.level)
    if a.cmd == "check":
        return cmd_check(a.plugin, a.base)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: Make it executable and smoke-test the CLI**

Run:
```bash
chmod +x scripts/semver_judge.py
python3 scripts/semver_judge.py level --plugin cosmic-farmland --base origin/main
```
Expected: prints one of `patch` / `minor` / `major` (no traceback). On this branch (PR #26 added skill-stats) expect `minor`.

- [ ] **Step 3: Verify the pure-function suite still passes**

Run: `python3 -m unittest tests.test_semver_judge -v`
Expected: PASS (Task 1–3 tests unaffected; this task added only git I/O).

- [ ] **Step 4: Commit**

```bash
git add scripts/semver_judge.py
git commit -m "feat(semver): git wrappers + level/set/check CLI"
```

---

## Task 5: bin/bump — human apply wrapper

**Files:**
- Create: `bin/bump`

- [ ] **Step 1: Write the wrapper**

```bash
# bin/bump
#!/usr/bin/env bash
# Apply a semver level to a plugin's manifest, idempotently, from origin/main.
# Used when pre-push blocks with "Run: bin/bump <level> <plugin>".
#
#   bin/bump minor                  # default plugin: cosmic-farmland
#   bin/bump major obsidian-weaver
set -euo pipefail

LEVEL="${1:?usage: bin/bump <patch|minor|major> [plugin]}"
PLUGIN="${2:-cosmic-farmland}"
REPO_ROOT="$(git rev-parse --show-toplevel)"

python3 "$REPO_ROOT/scripts/semver_judge.py" set \
  --plugin "$PLUGIN" --base origin/main --level "$LEVEL"

git add "$REPO_ROOT/plugins/$PLUGIN/plugin.json"
echo "[bump] staged plugins/$PLUGIN/plugin.json — commit and re-push"
```

- [ ] **Step 2: Make executable and smoke-test (no-op expected on a correct branch)**

Run:
```bash
chmod +x bin/bump
bin/bump minor
```
Expected: `set: cosmic-farmland already 1.10.0 (>= minor); no change` (branch is already correctly at minor). No version mutation.

- [ ] **Step 3: Commit**

```bash
git add bin/bump
git commit -m "feat(semver): bin/bump human apply wrapper"
```

---

## Task 6: pre-commit — idempotent floor from staged diff

**Files:**
- Modify: `.githooks/pre-commit`

- [ ] **Step 1: Replace the always-patch body**

Rewrite `.githooks/pre-commit` in full:

```bash
#!/usr/bin/env bash
# Auto-bump each touched plugin to its deterministic FLOOR (not always patch),
# computed from the staged diff structure. Idempotent + raise-only: anchored to
# origin/main, so repeated commits on a branch don't double-count, and a manual
# higher bump is never lowered. pre-push recomputes over the full range
# (including commit-message types) and blocks if this under-bumped.
#
# Why: Claude Code plugin caches key off plugins/<name>/plugin.json version.
# A new skill is a MINOR (new invokable surface); a removed skill is a MAJOR.
# The old always-patch bump mislabeled both — see docs/plans/semver-judgment.md.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
JUDGE="$REPO_ROOT/scripts/semver_judge.py"
[ -f "$JUDGE" ] || exit 0

CHANGED=$(git diff --cached --name-only --diff-filter=ACMRD)
[ -z "$CHANGED" ] && exit 0

TOUCHED_PLUGINS=$(printf '%s\n' "$CHANGED" \
  | awk -F/ '/^plugins\// && NF >= 2 {print $2}' \
  | sort -u)
[ -z "$TOUCHED_PLUGINS" ] && exit 0

# Use origin/main as the bump anchor when available (idempotency across commits).
BASE="origin/main"
git rev-parse --verify --quiet "$BASE" >/dev/null 2>&1 || BASE="HEAD"

while IFS= read -r plugin; do
  [ -z "$plugin" ] && continue
  manifest="plugins/$plugin/plugin.json"
  [ -f "$REPO_ROOT/$manifest" ] || continue

  # Did anything OTHER than the manifest change in this plugin?
  non_manifest=$(printf '%s\n' "$CHANGED" \
    | grep "^plugins/$plugin/" | grep -v "^$manifest$" || true)
  [ -z "$non_manifest" ] && continue

  level=$(python3 "$JUDGE" level --plugin "$plugin" --base "$BASE" --staged)
  python3 "$JUDGE" set --plugin "$plugin" --base "$BASE" --level "$level" >&2
  git add "$REPO_ROOT/$manifest"
done <<< "$TOUCHED_PLUGINS"

exit 0
```

- [ ] **Step 2: Smoke-test the hook against the current tree**

Run (stages a trivial skill edit, runs the hook body, then unstages):
```bash
touch plugins/cosmic-farmland/skills/next/SKILL.md
git add plugins/cosmic-farmland/skills/next/SKILL.md
bash .githooks/pre-commit
git restore --staged plugins/cosmic-farmland/skills/next/SKILL.md
```
Expected: prints a `set:` line (a modify of an existing skill → `patch` floor → since branch already minor-ahead, `set` reports "already ... no change"). No traceback, exit 0.

- [ ] **Step 3: Commit**

```bash
git add .githooks/pre-commit
git commit -m "feat(semver): pre-commit sets deterministic floor, not always-patch"
```

---

## Task 7: pre-push — level gate + summary, retire the differs-only check

**Files:**
- Modify: `.githooks/pre-push`
- Delete: `scripts/check-plugin-version.sh`

- [ ] **Step 1: Rewrite pre-push to call `check`**

```bash
#!/usr/bin/env bash
# Pre-push: enforcement gate (no CI in this repo by design).
#   1. semver gate -- recompute each touched plugin's required floor over
#      origin/main..HEAD (commit types + diff structure) and BLOCK if the
#      manifest under-bumped. Supersedes the old differs-only check: it asserts
#      the LEVEL is correct, not merely that the version changed. Prints a
#      one-line push summary per plugin (cross-repo awareness).
#   2. hook contract tests -- Stop/PreToolUse hooks gate every turn; a
#      regression must not reach main.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
JUDGE="$REPO_ROOT/scripts/semver_judge.py"

# Ensure origin/main is present locally for the range diff.
git fetch --quiet origin main 2>/dev/null || true

if [ -f "$JUDGE" ]; then
  TOUCHED=$(git diff --name-only origin/main...HEAD -- 'plugins/*' 2>/dev/null \
    | awk -F/ 'NF >= 2 {print $2}' | sort -u)
  for plugin in $TOUCHED; do
    [ -f "$REPO_ROOT/plugins/$plugin/plugin.json" ] || continue
    python3 "$JUDGE" check --plugin "$plugin" --base origin/main
  done
fi

if [ -d "$REPO_ROOT/tests" ]; then
  python3 -m unittest discover -s "$REPO_ROOT/tests" >/dev/null
  echo "hook tests pass"
fi
```

- [ ] **Step 2: Delete the superseded script**

Run: `git rm scripts/check-plugin-version.sh`
Expected: staged deletion. (Internal script, not a plugin surface — patch-level change. `check` is strictly stronger.)

- [ ] **Step 3: Smoke-test the gate on the current branch**

Run:
```bash
git fetch --quiet origin main 2>/dev/null || true
python3 scripts/semver_judge.py check --plugin cosmic-farmland --base origin/main
echo "exit=$?"
```
Expected: prints `cosmic-farmland 1.9.x->1.10.0 (minor): +skill skill-stats` (or similar added-skill summary) and `exit=0`. If it prints `FAIL ... Run: bin/bump` the branch genuinely under-bumped — fix with the printed command.

- [ ] **Step 4: Run the full hook test suite (must still pass)**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS — `test_semver_judge` (Task 1–3) **and** the existing `test_hooks` suite.

- [ ] **Step 5: Commit**

```bash
git add .githooks/pre-push
git commit -m "feat(semver): pre-push gates the bump LEVEL, drops differs-only check"
```

---

## Task 8: End-to-end verification (under-bump must block)

**Files:** none (verification only)

- [ ] **Step 1: Prove the gate blocks a deliberate under-bump**

Construct a throwaway scenario: force the manifest below its required level and confirm `check` fails.

Run:
```bash
# Temporarily pin manifest to the base version (simulating "forgot to bump").
BASE_V=$(git show origin/main:plugins/cosmic-farmland/plugin.json | jq -r .version)
jq --arg v "$BASE_V" '.version=$v' plugins/cosmic-farmland/plugin.json > /tmp/m.json
cp plugins/cosmic-farmland/plugin.json /tmp/m.bak
mv /tmp/m.json plugins/cosmic-farmland/plugin.json
python3 scripts/semver_judge.py check --plugin cosmic-farmland --base origin/main; echo "exit=$?"
# Restore.
mv /tmp/m.bak plugins/cosmic-farmland/plugin.json
```
Expected: prints `FAIL: cosmic-farmland needs minor ... Run: bin/bump minor cosmic-farmland` and `exit=1`. After restore, `git diff plugins/cosmic-farmland/plugin.json` is empty.

- [ ] **Step 2: Prove bin/bump fixes it idempotently**

Run:
```bash
BASE_V=$(git show origin/main:plugins/cosmic-farmland/plugin.json | jq -r .version)
cp plugins/cosmic-farmland/plugin.json /tmp/m.bak
jq --arg v "$BASE_V" '.version=$v' plugins/cosmic-farmland/plugin.json > /tmp/m.json && mv /tmp/m.json plugins/cosmic-farmland/plugin.json
bin/bump minor                      # should raise to base+minor
bin/bump minor                      # second run: no-op
git restore --staged plugins/cosmic-farmland/plugin.json 2>/dev/null || true
mv /tmp/m.bak plugins/cosmic-farmland/plugin.json
```
Expected: first `bin/bump` prints `set: cosmic-farmland <base> -> <base+minor> (minor ...)`; second prints `already ... no change`. Tree restored after.

- [ ] **Step 3: Final full-suite gate**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 4: Commit (if any verification helper or doc tweak was needed)**

```bash
git add -A
git commit -m "test(semver): end-to-end gate verification notes" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage (docs/plans/semver-judgment.md):**
- §1 Floor (cc-type → level) → Task 1 (`message_level`).
- §2 Major contract (removed/renamed identifier; add=minor) → Task 2 (`diff_level`, `_is_identifier_path`).
- §3 Removed/renamed grep blocks → Task 2 (major from D/R) + Task 7 (`check` exit 1).
- §4 Placement: idempotent pre-commit → Task 6; pre-push block with `bin/bump` one-liner → Task 5 + Task 7.
- §5 One-line push summary, no INVENTORY.md → Task 4 (`_summary_changes`, `cmd_check` print).
- Human override (manual higher bump never lowered) → Task 4 (`set`/`check` raise-only via `infer_level`).
- Deferred claude reviewer → intentionally absent. Correct for v1.

**Placeholder scan:** none — every code step is complete.

**Type consistency:** `message_level`, `diff_level`, `floor_level`, `bump_version`, `infer_level`, `_is_identifier_path`, `rank`, `max_level` are defined in Tasks 1–3 and called with matching signatures in Task 4. CLI subcommands `level`/`set`/`check` match `bin/bump` (Task 5) and both hooks (Tasks 6–7). Manifest path helper `_manifest_path` used consistently.

**Known v1 limitation (intentional, documented):** `diff_level` keys off file add/delete/rename of identifier paths, not on removed `name:` frontmatter lines or changed parsed-output value formats. Those are the deferred-reviewer's job (docs/plans/semver-judgment.md "Deferred"). Listed here so it isn't mistaken for a gap.
