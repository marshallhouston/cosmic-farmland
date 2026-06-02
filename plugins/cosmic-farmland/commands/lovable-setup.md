---
description: De-brand + configure a freshly-exported Lovable app (tests, deps, tokensave, Railway/GitHub).
argument-hint: "[project-dir] (default: current dir)"
---

Run the bundled `lovable-setup` script on the target Lovable project.

- Target dir: `$ARGUMENTS` if given, else the current working directory.
- Invoke via Bash: `${CLAUDE_PLUGIN_ROOT}/scripts/lovable-setup $ARGUMENTS`
  (self-contained in the plugin, so it travels with `/plugin install` and across
  machines; also on PATH as `lovable-setup` if you ran `bin/install.sh`).
- Interactive: it prompts for in-range dep updates, the @lovable.dev wrapper swap
  (TanStack-SSR shape only; build-gated + auto-rollback), history squash, GitHub
  repo creation, and Railway setup. Surface its prompts to the user; do not
  auto-answer the destructive steps (history squash, repo creation).
- Idempotent — safe to re-run; every step no-ops if already done.
- After it finishes, relay the summary line and the one manual step it prints
  (GitHub->Railway auto-deploy is OAuth dashboard-only).


## Supported project shapes

Auto-detected (precedence: docker → tanstack-ssr → static):

| Shape | Signal | Deploy |
|-------|--------|--------|
| `docker` | a `Dockerfile` is present | Railway builds the image |
| `tanstack-ssr` | `@tanstack/react-start` in `package.json` | bun-serve shim (`server-entry.ts`), `bun run start` |
| `static` | plain Vite SPA (default) | `bunx serve dist -s` |

**TanStack Start SSR.** Lovable's TanStack template (`@lovable.dev/vite-tanstack-config`,
`tanstack_start_ts_*`) builds to `dist/server/server.js` — a Web `{ fetch(req, env, ctx) }`
handler that does **not** listen on a port. The script writes `server-entry.ts`, a
bun-native shim that wraps that handler with `Bun.serve`, serves `dist/client` assets, and
listens on `$PORT`. Runtime is always bun (never node-server).

De-brand attempts to replace the `@lovable.dev` wrapper with a plain TanStack Start + Vite
config. The swap is **build-gated**: if the rebuild fails it auto-restores the wrapper
(`vite.config.ts.bak`) — the shim deploys the wrapper's output either way, so deploy never
depends on the swap succeeding. It also de-brands the head/`<title>`/og strings in
`src/routes/__root.tsx` (leaving functional imports like `lovable-error-reporting` intact).

Tested against shapes: `tanstack-ssr` (dead-77-odyssey).
