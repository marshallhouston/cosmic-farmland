---
name: deps-sweep
description: "Dependency bump workflow for any bun repo. Buckets `bun outdated` into safe-batch / majors / exact-pinned / peer-held, runs `bun audit`, opens one PR per bucket, ships each. Triggers: /deps-sweep, 'bump deps', 'what needs to be bumped', 'deps audit'."
---

# /deps-sweep

Repo-agnostic. Verify commands and prod check come from the repo's own `CLAUDE.md` under a `## Deps sweep` heading; parked deps come from `.deps-held` at the repo root. Do not fork this skill into a repo.

## 0. Load repo context

Read the repo's `CLAUDE.md` for a `## Deps sweep` section. It supplies:
- **Verify** commands (typecheck / build / test). Fallback if absent: `bun run build && bun run test`.
- **Prod check** (URL to curl, or deploy dashboard to eyeball). Skip if the repo has none.
- Any repo-specific traps worth knowing before you bump (peer ordering, a post-bump install step).

Parked deps live in `.deps-held` at the repo root, not in prose, because the script reads them:

```
# <dep> | <why it is parked, and what unparks it> | <optional probe>
typescript | TS 7 has no programmatic API, so `astro check` refuses to run. Tracked at ... | npm info @astrojs/check peerDependencies.typescript | grep -q 7 && echo "peer admits TS 7 now"
```

The reason is one field; **the probe is everything after it**, so it can contain pipes. The probe runs on every audit and prints under the entry. Write it to stay **silent while the gate is shut** and speak only when the dep becomes takeable, otherwise it is noise everyone learns to skip. A HELD row with no probe is just a slower "never".

If the sweep teaches you something durable, write it back: a trap goes in the CLAUDE.md section, a parked dep goes in `.deps-held`. Those are the only per-repo artifacts this skill creates.

## 1. Bucket

Run `bash "${CLAUDE_PLUGIN_ROOT}/skills/deps-sweep/scripts/deps-audit.sh"` from anywhere in the repo. Five buckets:

- **HELD** — listed in `.deps-held`. Do NOT bump. Checked before every other bucket, so a breaking semver-minor cannot slip into SAFE BATCH, the one bucket that says "bump without thinking".
- **SAFE BATCH** — patch/minor where `update` == `latest`. One PR for all.
- **MAJORS** — latest major > current major. One PR per dep, after the safe batch lands.
- **EXACT-PINNED** — `update` < `latest` only because package.json pins an exact version (no `^`/`~`). Not peer-blocked. Edit the pin to bump; verify the new version's peers first with `npm info <dep>@<latest> peerDependencies`. Own PR.
- **PEER-HELD** — `update` < `latest` under a caret/range spec, genuinely blocked on a peer dep. Bump alongside the core dep in a follow-up.

`--self-test` runs the bucketing and `.deps-held` parsing checks with no network and no repo state. Run it after editing the script.

## 2. Audit

**Run `bun audit` too.** `bun outdated` only sees direct deps at the wrong version. It is blind to a current direct dep dragging a vulnerable transitive tree. Triage each advisory by whether the vulnerable copy is actually reachable in prod:

- Read the dependency path the audit prints. A second copy under a dev-only tool is not a prod exposure, and a peer dep resolves to the root version rather than the vulnerable one.
- Reachable in prod: fix in this sweep, own PR.
- Build-time only, dev-only, trusted-input, or platform-inapplicable (a Windows-only CVE on a macOS/Linux repo): note it, no action.
- No fix available upstream: a wait, not a task.
- **Fix by bumping the parent.** Most advisories are transitive under one framework dep. Bump that one, re-run `bun audit`, re-triage what is left.
- **The fix is often a delete.** Check `npm info <dep> version` first: if latest is already the vulnerable version, bumping can never clear it. Then grep importers. Zero importers means remove the dep. (preach-hub #1018: `@better-auth/cli` was one-time scaffolding pinning its own stale `better-auth`; deleting it took 21 advisories to 7.)

## 3. Safe batch PR

Worktree per sweep. `bun update <name> ...` for every dep in the batch. Run the repo's verify commands. If a new lint or typecheck rule fires (eslint-plugin-react-hooks 7.1 is the classic), hold that one dep, ship the rest, file a follow-up for the holdouts.

Pre-existing verify failures are not yours. Confirm against the base branch before you chase one.

## 4. Each major, separately

Worktree per dep. Before bumping, **grep usage**: `grep -rn "<dep-name>\|<dep-export>" src scripts`. Zero importers means **delete the dep** rather than migrate. (preach-hub #533: react-day-picker v10 was a delete, not a migration.) If used, bump and fix breaking changes in the same PR.

## 5. Exact-pinned / peer-held

Exact-pinned: edit the pin in package.json to latest, `bun install`, grep usage, verify peers, own PR. (preach-hub #597: `@anthropic-ai/sdk` was exact-pinned, not peer-blocked.) Peer-held: follow-up PR after the core dep lands. Confirm by re-running the audit; the entry should drop to safe-batch on the next pass.

## 6. Ship each

`gh pr merge <pr> --squash`, then worktree + branch cleanup. Run the repo's prod check on the post-merge deploy.

## 7. Final

`bun outdated` empty, or majors-only plus anything HELD. Re-run `bun audit` and confirm the remaining count is only the no-action set from step 2.

## Notes

- **`bun outdated` is not a security check.** Every direct dep can be current while a stale transitive tree sits underneath. Run `bun audit` every sweep. The preach-hub 2026-08-28 pass finished with a clean-looking 2 outdated and 21 advisories including a critical. That is what step 2 exists to catch.
- **No Dependabot.** Manual judgment beats bot noise: a bot would have filed a v9 to v10 migration on react-day-picker; manual found it was dead code.
- **PR scope discipline.** Safe batch = one PR. Majors = separate. Lint-rule fixes triggered by a plugin bump = separate PR.
- **Force-push on rebase.** PRs in the batch may conflict in `package.json` + `bun.lock` after the first merge. Reset to `origin/main`, `bun install`, re-apply the single bump with `bun add`, force-push the feature branch.
