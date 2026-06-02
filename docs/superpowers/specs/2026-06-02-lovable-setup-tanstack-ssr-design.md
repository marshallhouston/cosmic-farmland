# lovable-setup: TanStack-Start SSR support

**Date:** 2026-06-02
**Status:** Approved (design) — pending spec review
**Script:** `plugins/cosmic-farmland/scripts/lovable-setup`
**Skill:** `plugins/cosmic-farmland/skills/lovable-setup/SKILL.md`

## Problem

`lovable-setup` was built for the plain Vite-React SPA shape Lovable used to export.
Lovable now frequently ships a **TanStack Start SSR** variant
(`@tanstack/react-start` + `nitro`, wrapped by `@lovable.dev/vite-tanstack-config`,
template `tanstack_start_ts_*`). On that shape the current script does the wrong thing:

1. **Start script is wrong.** No `Dockerfile` → script assumes static SPA → injects
   `bunx serve dist -s`. But the SSR build emits `dist/server/server.js`, a
   *cloudflare/edge-style fetch handler* (`export default { fetch(req, env, ctx) }`)
   that does not listen on a port. Static-serving `dist` skips SSR entirely.
2. **De-brand is warn-only.** `componentTagger` is bundled inside the `@lovable.dev`
   wrapper, not strippable by `sed`. The head/`<title>`/og-image live in
   `src/routes/__root.tsx`, not an HTML file — the current HTML-only de-brand misses them.
3. **Build-verify points at the wrong output dir** for this shape.

The script must detect the shape and do the right thing per shape, robustly enough to
survive the variety of Lovable exports (and Lovable template-version churn).

## Decisions (locked with user)

- **Runtime is always bun.** The prod runtime must be bun-native (`Bun.serve`), never
  node-server. Build-time toolchain (vite + nitro bundling) is unconstrained — bun runs
  vite for the build regardless.
- **Deploy via a bun-serve shim**, not nitro's `node-server` preset. The preset emits a
  node-`http`-based server; running it under bun is still node semantics. Rejected.
- **De-brand replaces the `@lovable.dev` wrapper** with plain config — but the swap is
  **build-gated and reversible** (a bash script cannot safely sed-rewrite the wrapper
  across arbitrary Lovable versions, so we attempt + verify + auto-rollback).

## Shape detection

Add an explicit shape variable. Precedence: `docker` → `tanstack-ssr` → `static`.

| Shape | Signal | Deploy |
|-------|--------|--------|
| `docker` | `Dockerfile` present | Railway builds the image (unchanged) |
| `tanstack-ssr` | `@tanstack/react-start` in `package.json` deps (cross-check `.lovable/project.json` `template` matches `tanstack_start*`) | bun-serve shim |
| `static` | else (plain Vite SPA) | `bunx serve <out> -s` (unchanged) |

`@tanstack/react-start` in deps is the canonical signal; `.lovable/project.json` is a
secondary confirmation, not required (de-branded repos may delete it).

## Component 1 — bun-serve shim (the single SSR runner)

Generate a committed `server-entry.ts` at repo root:

```ts
// server-entry.ts — bun-native prod runtime for TanStack Start SSR.
// Wraps the built fetch handler and serves client statics on $PORT.
const entry =
  (await Bun.file("./dist/server/server.js").exists())
    ? "./dist/server/server.js"
    : "./.output/server/index.mjs"; // fallback if a future build emits nitro layout
const app = (await import(entry)).default as {
  fetch: (req: Request, env: unknown, ctx: unknown) => Response | Promise<Response>;
};
const port = Number(process.env.PORT ?? 3000);
Bun.serve({
  port,
  async fetch(req) {
    const url = new URL(req.url);
    if (url.pathname !== "/") {
      const file = Bun.file(`./dist/client${url.pathname}`);
      if (await file.exists()) return new Response(file);
    }
    return app.fetch(req, process.env, {});
  },
});
console.log(`SSR listening on :${port}`);
```

- `package.json`: add `"start": "bun server-entry.ts"` (only for `tanstack-ssr`; static
  keeps `bunx serve`, docker keeps none).
- Idempotent: skip if `server-entry.ts` already present and `"start"` already set.
- Static-asset rule: serve `dist/client/<path>` when the file exists, else fall through
  to the SSR handler. `/` always goes to SSR (HTML is rendered, not a static file).
- `app.fetch(req, process.env, {})` — env/ctx are best-effort; the SSR handler ignores
  them in practice. Verified by the boot smoke check below.

## Component 2 — de-brand wrapper replacement (build-gated, reversible)

Only when `@lovable.dev/vite-tanstack-config` is detected:

1. Copy `vite.config.ts` → `vite.config.ts.bak`.
2. Write a plain config template that **preserves the fetch-handler output contract**
   (so Component 1's shim keeps working) and drops only the Lovable-only plugins
   (componentTagger, error-logger, sandbox detection). Replicates: `tanstackStart`,
   `viteReact`, `@tailwindcss/vite`, `vite-tsconfig-paths`. (`VITE_*` env injection and
   the `@` alias come free from vite + tsconfigPaths.)
3. Swap deps: `bun remove @lovable.dev/vite-tanstack-config`; `bun add -d
   @vitejs/plugin-react @tailwindcss/vite vite-tsconfig-paths` (only those missing).
4. **Gate:** rebuild. If the build succeeds and still emits `dist/server/server.js`,
   keep the change and delete the `.bak`. If it fails (or output shape changed),
   **restore `vite.config.ts.bak`, re-add the wrapper dep, and warn**: "wrapper
   replacement needs manual review — left the Lovable wrapper in place."
5. Also de-brand `src/routes/__root.tsx`: replace Lovable `<title>` / og-image strings
   with the project name (best-effort `sed`, same spirit as the HTML pass).

Replacement is guarded behind a confirm prompt (`ask`), like the other destructive steps.
On non-TTY runs it auto-skips (keeps the wrapper) — safe default.

## Component 3 — build-verify per shape

- `static`: unchanged (`dist` or `dist/client`).
- `tanstack-ssr`: after `bun run build`, assert `dist/server/server.js` exists; then boot
  the shim (`PORT=<free> bun server-entry.ts &`), `curl -fsS localhost:$PORT/` returns
  2xx, kill it. Fail the run if the smoke check fails.
- `docker`: unchanged.

## Unchanged (already shape-agnostic)

Lockfile cleanup, `.gitignore`, `.railwayignore`, Vitest scaffold, pre-push deploy gate,
CLAUDE.md scaffold + conventions tail, tokensave init, history-squash guard, GitHub push,
Railway init. Railway's per-shape start-command guidance updates to mention `bun run
start` for `tanstack-ssr`.

## Error handling

- Shape detection defaults to `static` if no SSR/Docker signal — preserves current behavior.
- Wrapper replacement: any failure → full rollback from `.bak`, never leaves a broken
  `vite.config.ts`. The `.bak` is git-ignored noise; clean it on success.
- Shim boot smoke-check failure aborts before push (consistent with the existing
  "tests fail → stop" gate).
- All steps remain idempotent and re-runnable.

## Testing

`bin/` scripts in cosmic-farmland have no harness today. Verification plan:
1. **This repo (`dead-77-odyssey`)** is the live `tanstack-ssr` fixture — run the updated
   script end-to-end (minus push), confirm shim boots + serves SSR.
2. **A plain Vite SPA export** (or synthetic fixture) — confirm `static` path unchanged.
3. Confirm idempotent re-run (second pass no-ops).
Add a short "Tested against shapes: …" note to the skill doc.

## Out of scope

- Auto-deploy wiring GitHub → Railway (remains the one OAuth-dashboard manual step).
- Non-Lovable TanStack Start projects (signal-compatible, but untested).
- Cloudflare/edge deploy targets (we standardize on Railway + bun).
