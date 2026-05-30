# cosmic-farmland semver judgment system

Status: design locked (grill-me 2026-05-30, PTV-huff TRIM 2026-05-30). No code yet.

## Goal

Pick major/minor/patch for the cosmic-farmland plugin with judgment, not blind
patch. Aware across repos (I edit the plugin from other repos).

## Why (the recent pain)

`.githooks/pre-commit` auto-bumps PATCH always and trusts the human to pre-bump
minor/major. PR #26 added a new skill (skill-stats) and had to be **hand-fixed
to 1.10.0** — a minor the system bumped as patch. That hand-fix is the bug.

## Core shape (v1 — deterministic only)

Deterministic floor (cc-type -> level) + a removed/renamed-identifier grep. No
model. The version **always** bumps on a plugin-touching push.

PTV-huff cut the `claude -p` reviewer from v1 — see **Deferred** below. The
locked major contract (section 2) is grep-detectable, which designed the model
out of its own job. claude was a primitive in search of a problem; ship the
floor first, log mis-bumps, add claude only if the log proves it.

## 1. Floor (deterministic)

Conventional-commit type -> level:

- `feat` -> minor
- `fix` / `perf` / `refactor` / `docs` / `chore` / `test` -> patch
- `!` or `BREAKING CHANGE:` -> major

Computed over the push range relative to `origin/main`. Highest level in the
range wins.

## 2. Major definition (the consumer contract)

Semver major = **breaking**, not big. A 10x new feature that breaks nothing is a
minor. The "this feels like a 2.0" instinct is marketing versioning, a different
axis — deliberately discarded.

**Auto-major = breakage only:**

1. Removed/renamed invokable identifier — skill `name:`, command file, agent.
   (`/foo` -> "Unknown command".)
2. Removed/renamed field in machine-parsed output — JSON key, report column,
   settings key a downstream reads.

Both reduce to: *a named thing a consumer references got removed or moved.*

**Explicitly NOT major:**

- Add a skill/command/hook -> minor.
- Hook policy change / threshold flip / behavior reversal **with same I/O shape**
  -> minor. (Interface intact; only the decision changed. Includes fail-open ->
  fail-closed: disruptive but visible, reversible, no interface broke.)
- Big new functionality, totally different -> minor (still no break).
- Internal `scripts/` refactor, docs, templates -> patch.

The asymmetry: **adding is safe; removing/renaming is breaking.**

**Human override:** `BREAKING CHANGE:` / `--major` for a deliberate identity
relaunch (rip out half the skills, re-theme, call it 2.0). The machine **never
infers** this — opt-in only.

## 3. Removed/renamed grep

Scans the diff for vanished/renamed invokable identifiers (section 2.1) +
removed parsed-output fields (section 2.2). A clear major signal **blocks** the
push. Deterministic, no model. This is the entire major-detection mechanism for
v1.

## 4. Placement

- **pre-commit:** idempotent floor bump. Bumps once per push-range to the
  highest level the range earns — first `feat` takes 1.10->1.11; later commits
  this branch see "already minor-ahead of main" -> no further bump. Kills the
  per-commit double-count. 90% case: version already correct at push time.
- **pre-push:** recompute floor + grep over the full range. If the result
  **exceeds** what's in `plugin.json` (mislabel across commits, or a grep major
  signal) -> **block** with the exact `bin/bump <level>` one-liner. Apply,
  re-push. **No history rewrite** — pre-push is a gate, not a mutator.

CI/GitHub Action path is **off the table** (dropped in fe3b171).

## 5. Cross-repo awareness

Editing plugin files from another repo still commits *in* cosmic-farmland, so its
githooks fire normally. The only blind spot is *seeing* state. Close it with a
one-line push summary:

```
cosmic-farmland 1.10->1.11 (minor): +skill activity-stats
```

- **No committed INVENTORY.md** — another artifact that rots.
- On-demand `bin/inventory` script (reads the tree live) later, only if friction
  proves the need.

## v1 scope (one PR)

Floor + grep + idempotent pre-commit + pre-push block + one-line push summary.
No model, no json parsing, no fail-open matrix, no timeout tuning.

While running v1, **log every floor mis-bump**: cases where the deterministic
level was wrong and it mattered (not just cosmetic). That log is the entry
criterion for the deferred claude reviewer.

---

## Deferred — claude reviewer (DEFER, not BUILD)

A gated `claude -p` second opinion that can only *raise* the floor on ambiguous
diffs. Cut from v1 by PTV-huff: it handled three cases (mislabeled commit type,
rename-vs-delete+add, subtle value-format break) that have **never been
observed**, on a single-consumer plugin where a wrong bump is fixed by bumping
again. The cost machinery (gate, context strip, haiku, json parse, 4-way
fail-open, timeout, max/enum guards) all existed *only because* claude was in
the design.

**What would flip DEFER -> BUILD:** a real log from v1 with >=2-3 cases where
(a) the wrong level actually shipped, (b) it mattered to a consumer, and (c) a
diff-reading model would have caught what the grep could not.

If it earns in, the shape was: floor < major gate + removed/rename-or-hook-modify
diff trigger, haiku, stripped context, `--output-format json` enum
`{patch,minor,major}`, `final = max(floor, claude_level)`, fail-open on
absent/offline/unauthed/hung, deterministic grep still blocks without it.

## Frozen context

- Repo: cosmic-farmland, branch `feat/skill-stats`, PR #26, this PR hand-fixed to
  1.10.0 (new skill = minor).
- `.githooks/pre-commit` today: auto-bumps PATCH always — the root miss.
- `.githooks/pre-push` today: `scripts/check-plugin-version.sh` (asserts version
  DIFFERS from origin/main, not that the level is correct) + python hook tests.
- `claude -p ... --output-format json` confirmed working headless, no API key
  (kept for the deferred reviewer).
