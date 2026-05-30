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
