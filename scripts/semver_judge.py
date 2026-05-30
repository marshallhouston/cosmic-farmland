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
