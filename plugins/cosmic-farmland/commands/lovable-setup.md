---
description: Take a freshly-exported Lovable app all the way to marshall's dev setup — de-brand, deps, lint, real tests, design.html, favicon + social link preview, deploy scaffolding.
argument-hint: "[project-dir] (default: current dir)"
---

Transition a freshly-exported Lovable app into marshall's dev setup. Two phases:
**mechanical** (the bundled script) then **judgment** (real tests + design system),
so the project lands fully configured, formatted, tested, and documented in one go.

## Phase A — mechanical (bundled script)

Run: `${CLAUDE_PLUGIN_ROOT}/scripts/lovable-setup $ARGUMENTS`

- Target dir: `$ARGUMENTS` if given, else the current working directory.
- Invoke via Bash: `${CLAUDE_PLUGIN_ROOT}/scripts/lovable-setup $ARGUMENTS`
  (self-contained in the plugin, so it travels with `/plugin install` and across
  machines; also on PATH as `lovable-setup` if you ran `bin/install.sh`).
- Handles, in order: lockfile cleanup, `.gitignore`/`.railwayignore`, de-brand
  (strip Lovable editor hooks + branding), favicon reset, start script, install,
  Vitest scaffold + pre-push deploy gate, **automatic in-range dep update**
  (`bun update`; majors reported, never auto-applied), **format + lint-fix**
  (normalizes the unformatted scaffold once), CLAUDE.md + conventions tail,
  tokensave index, build + test verify, history squash, GitHub repo, Railway.
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

Set `LOVABLE_SETUP_DEBRAND=1` to auto-confirm the wrapper swap non-interactively
(useful when an agent runs the script without a TTY, where prompts otherwise auto-skip).

Set `LOVABLE_SETUP_RAILWAY=1` to auto-create the Railway project + deploy in the
same non-interactive way (uses `railway up --ci`; `railway.json` supplies build/start).
The GitHub->Railway repo connect for push-to-deploy stays a one-time dashboard/OAuth step.

Tested against shapes: `tanstack-ssr` (dead-77-odyssey).

## Phase B — judgment (you, after the script succeeds)

The script handles everything deterministic. These steps need to read the
actual app, so you do them — in the project dir, committed as a follow-up.

### 1. Real component tests

The script leaves only a smoke test. Add real coverage:

- Read `src/components/` and skip `src/components/ui/` (shadcn primitives — not ours).
- For each *interactive* component (takes event-handler props like `onClick` /
  `onSelect` / `onHover`, or owns state), write a Vitest + Testing Library test
  covering its real behavior: highlight/selection logic, click vs double-click,
  hover precedence, the exact arguments passed to callbacks.
- Use minimal local fixtures, not the app's real data, so tests stay stable when
  content changes.
- If a test imports via the `@/` alias, ensure `vitest.config.ts` has a matching
  `resolve.alias` (`"@" -> ./src`); add it if missing.
- Run `BUN_OPTIONS= bun run test` until green (the `BUN_OPTIONS=` prefix is required under Claude Code: a session-injected `--preload` otherwise makes `bun run <script>` bail to help text and run nothing). Don't test purely-presentational components or `ui/`.

### 2. design.html — design-system reference

Generate a self-contained `design.html` at the project root: a one-page style guide
for the app's visual language, built by reading the *actual* styles (not invented).

- Source tokens from `src/styles.css` (or `index.css`) + the tailwind config:
  color palette (swatches + hex / CSS-var names), typography scale (font families
  and sizes taken from real headings/body), spacing + radius, any custom tokens.
- Include a component gallery: render representative samples (buttons, cards, badges,
  nav) using the project's *actual* class names so it mirrors the real look.
- Fully self-contained: inline CSS + fonts, no build step — opens straight in a browser.

### 3. Brand assets — favicon + link preview

Make the app presentable out of the box: a real favicon, and a rich preview when
the URL is shared via text / Slack / social. Reuse the design system from step 2
(accent color, fonts, app name).

**Favicon** — replace the setup placeholder (`public/favicon.svg`):

- Generate a simple branded SVG favicon — the app's initial (or a minimal mark) on
  the accent color, using the design-system palette. Scalable, no raster needed.

**Social link preview (Open Graph + Twitter card):**

- Build `public/og-image.png` at **1200×630**: author a styled HTML card (app name +
  tagline, design-system colors/fonts), then render it to PNG with a headless
  screenshot (the `agent-browser` skill, or any headless browser). Raster is required —
  iMessage / Slack / Twitter don't unfurl SVG. Keep the source HTML so the card is
  regenerable.
- Wire the head meta (in `index.html` for plain-vite, or the route `head()` in
  `src/routes/__root.tsx` / `index.tsx` for TanStack Start):
  `og:title`, `og:description`, `og:type=website`, `og:image` (+ `:width`/`:height`),
  `og:url` (placeholder for the deploy domain), `twitter:card=summary_large_image`,
  `twitter:image`. Reuse the existing title / description if already present.
- Verify: open `public/og-image.png` to confirm it renders, and check the meta is
  well-formed.

### 4. Commit the follow-up

Commit Phase B (tests + `design.html` + brand assets) on the setup branch with a clear
message. If the script already pushed, push the follow-up too.
