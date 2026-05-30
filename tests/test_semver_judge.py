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
