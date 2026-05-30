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


def _plugin_changed(plugin, base):
    """True if any file under plugins/<plugin>/ changed in base..HEAD."""
    prefix = "plugins/%s/" % plugin
    for ln in _status_lines(base, staged=False):
        for token in ln.split("\t")[1:]:
            if token.startswith(prefix):
                return True
    return False


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
    if not _plugin_changed(plugin, base):
        print("check: no %s changes in %s..HEAD; skip" % (plugin, base))
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
