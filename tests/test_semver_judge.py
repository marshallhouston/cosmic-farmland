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

    def test_breaking_change_in_later_commit_of_range(self):
        msgs = ["chore: a", "feat: b", "fix: c\n\nBREAKING CHANGE: x"]
        self.assertEqual(sj.message_level(msgs), "major")


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


class TestFloorComposition(unittest.TestCase):
    def test_diff_outranks_message(self):
        self.assertEqual(
            sj.floor_level(["fix: tweak"],
                           ["A\tplugins/cosmic-farmland/skills/new/SKILL.md"],
                           "cosmic-farmland"),
            "minor",
        )

    def test_message_outranks_diff(self):
        self.assertEqual(
            sj.floor_level(["feat: enhance"],
                           ["M\tplugins/cosmic-farmland/skills/next/SKILL.md"],
                           "cosmic-farmland"),
            "minor",
        )
