# /ship — incident log

Each guard in `ship.md` / `ship-poll.sh` / `ship-verify-deploy.sh` traces to a
real failure. Kept here (not inline) so the spec stays readable; the code already
encodes the fix.

## Poll loop (ship-poll.sh)

- **PR #479 (2026-05-07)** — foreground poll; user interrupted twice in 4 min thinking it hung. Fix: background + `Monitor`, heartbeat per tick.
- **PR #479 (2026-05-07)** — jq filtered only `.conclusion`, missed Railway `.state` pending, false-fell-through to merge mid-build. Fix: snapshot reads `.conclusion // .state`.
- **PR #319 (2026-04-26)** — sat OPEN 5 min after green because `auto-merge-green` only fires on classify completion and the label was applied manually after. Fix: fall through to manual merge as soon as all-green (READY).
- **PR #431 (2026-05-03)** — preach-hub killed GHA (#419), `statusCheckRollup` permanently empty, so the `PASSED>0` branch never matched and it stalled the full 5 min. Fix: 60s grace → READY_NO_CHECKS for CI-less repos.

## Prod-verify (ship-verify-deploy.sh)

- **PR #421 (2026-05-01)** — merged green, but prod pre-deploy had been silently failing since #419 (a test-setup guard rejected the mainline DB; PR-preview used switchyard so the gap was invisible). Surfaced only when a user hit an unrelated service. Reason for the step existing at all.
- **PR #428** — uncapped `rw` call hung 17 min. Fix: hard per-call timeout.
- **PR #449** — coreutils missing, no perl fallback wired, hung on `rw deployment list`. Fix: gtimeout → timeout → perl → fail-loud chain.
- **2026-05-04** — every preach-hub /ship false-negatived on auth and skipped prod-verify because it judged `railway status` by exit code; project tokens exit non-zero even when the project resolves. Fix: judge auth by `^Project:` on stdout.
- **lenny-explorer (2026-05-27)** — a hardcoded `src/server/`-style deploy-path allowlist false-skipped a ship whose frontend ships inside the Docker image (a `src/components/` diff matched nothing). Fix: diff-gate is fail-safe — verify unless the diff is provably inert (docs/test/CI only), no per-repo allowlist.
