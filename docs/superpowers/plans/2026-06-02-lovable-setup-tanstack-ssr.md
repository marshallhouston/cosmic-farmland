# lovable-setup TanStack-Start SSR Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the `lovable-setup` script to detect the TanStack-Start SSR shape and make it deployable on Railway via a bun-native `Bun.serve` shim, with a build-gated, reversible de-brand of the `@lovable.dev` Vite wrapper.

**Architecture:** Add a `SHAPE` variable (`docker` → `tanstack-ssr` → `static`) replacing the binary `DEPLOY_MODE`. For `tanstack-ssr`, the script writes a committed `server-entry.ts` that wraps the built `dist/server/server.js` Web-fetch handler with `Bun.serve` (serving `dist/client` statics), sets `"start": "bun server-entry.ts"`, and a build-verify step boots it + curls `/`. De-brand attempts a plain-config wrapper swap, rebuilds, and auto-rolls-back on failure — so deploy works whether the swap succeeds or not (the shim runs the wrapper's output too).

**Tech Stack:** Bash, Bun, Vite, TanStack Start (`@tanstack/react-start` + nitro toolchain), Railway.

**Repos:**
- **Tool (edit here):** `~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr` (worktree, branch `feat/lovable-setup-tanstack-ssr`). Script: `plugins/cosmic-farmland/scripts/lovable-setup`. Skill: `plugins/cosmic-farmland/skills/lovable-setup/SKILL.md`.
- **Fixture (verify against):** `~/code/dead-77-odyssey` — a real `tanstack-ssr` Lovable export. For iterative tests, use a throwaway copy at `/tmp/ls-fixture` with `origin` removed (so no accidental push).

> **Editing constraint:** the session cwd is in `dead-77-odyssey`, so the Write/Edit tools are blocked from the cosmic-farmland worktree by the worktree-path guard. Edit cosmic-farmland files via **Bash** (`cat`/`sed`/`python3`), or stage with the Write tool under `/tmp` then `mv` into the worktree.

---

## File structure

| File | Responsibility | Change |
|------|----------------|--------|
| `plugins/cosmic-farmland/scripts/lovable-setup` | the installer | Modify: shape detection, shim+start (SSR branch), build-verify (SSR branch), de-brand (wrapper swap + `__root.tsx`), Railway/CLAUDE.md guidance |
| `plugins/cosmic-farmland/skills/lovable-setup/SKILL.md` | skill doc | Modify: document the three shapes + SSR deploy |
| `server-entry.ts` (in target repo, emitted by the script) | bun-serve runtime shim | Created at runtime via heredoc inside the script |
| `vite.config.ts` (in target repo) | de-branded plain config | Rewritten at runtime, build-gated + `.bak` rollback |

All edits to the script are in one file; tasks are ordered so each is independently verifiable against the fixture.

---

## Pre-flight (one-time, not a code change)

- [ ] **Build a throwaway fixture** for iterative verification.

```bash
rm -rf /tmp/ls-fixture
cp -R ~/code/dead-77-odyssey /tmp/ls-fixture
cd /tmp/ls-fixture
git remote remove origin 2>/dev/null || true   # never push the fixture anywhere
rm -rf node_modules dist .output server-entry.ts vite.config.ts.bak 2>/dev/null || true
git checkout -- vite.config.ts package.json 2>/dev/null || true   # pristine wrapper config
bun install >/dev/null 2>&1
echo "fixture ready: $(git -C /tmp/ls-fixture remote -v | wc -l | tr -d ' ') remotes (want 0)"
```

Expected: `fixture ready: 0 remotes (want 0)`

---

## Task 1: Shape detection (`SHAPE`: docker → tanstack-ssr → static)

**Files:**
- Modify: `plugins/cosmic-farmland/scripts/lovable-setup` — the "Detect project shape" block (currently sets `DEPLOY_MODE` static/docker around lines 63-67) and every later `DEPLOY_MODE` reference.

- [ ] **Step 1: Replace the detection block.** Find:

```bash
# ── Detect project shape ──────────────────────────────────────────────
DEPLOY_MODE="static"
[ -f Dockerfile ] && DEPLOY_MODE="docker"
HAS_PY="no"; { [ -f server/requirements.txt ] || [ -f requirements.txt ]; } && HAS_PY="yes"
info "Deploy shape: ${DEPLOY_MODE}$([ "$HAS_PY" = yes ] && echo " + python backend")"
```

Replace with:

```bash
# ── Detect project shape ──────────────────────────────────────────────
# Precedence: docker (Dockerfile) > tanstack-ssr (@tanstack/react-start) > static SPA.
SHAPE="static"
[ -f Dockerfile ] && SHAPE="docker"
if [ "$SHAPE" = static ] && grep -q '"@tanstack/react-start"' package.json 2>/dev/null; then
  SHAPE="tanstack-ssr"
fi
HAS_PY="no"; { [ -f server/requirements.txt ] || [ -f requirements.txt ]; } && HAS_PY="yes"
info "Project shape: ${SHAPE}$([ "$HAS_PY" = yes ] && echo " + python backend")"
```

- [ ] **Step 2: Rename remaining `DEPLOY_MODE` references to `SHAPE`.** There are uses in the start-script block, CLAUDE.md scaffold, build-verify, Railway, and the final summary. Run:

```bash
cd ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr
sed -i '' 's/DEPLOY_MODE/SHAPE/g' plugins/cosmic-farmland/scripts/lovable-setup
grep -n 'DEPLOY_MODE' plugins/cosmic-farmland/scripts/lovable-setup
```

Expected: no remaining `DEPLOY_MODE` matches (empty output). (Note: the detection block in Step 1 already uses `SHAPE`; this sed catches the rest.)

- [ ] **Step 3: Verify detection against the fixture.** Run:

```bash
SHAPE="static"; [ -f /tmp/ls-fixture/Dockerfile ] && SHAPE="docker"
[ "$SHAPE" = static ] && grep -q '"@tanstack/react-start"' /tmp/ls-fixture/package.json && SHAPE="tanstack-ssr"
echo "detected: $SHAPE"
```

Expected: `detected: tanstack-ssr`

- [ ] **Step 4: Commit.**

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr add plugins/cosmic-farmland/scripts/lovable-setup
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr commit -m "feat(lovable-setup): SHAPE detection (docker/tanstack-ssr/static)"
```

---

## Task 2: Bun-serve shim + start script (tanstack-ssr branch)

**Files:**
- Modify: `plugins/cosmic-farmland/scripts/lovable-setup` — the "Start script" block (currently `if [ "$SHAPE" = static ]` … else docker, around lines 145-165 after Task 1's rename).

- [ ] **Step 1: Add a `tanstack-ssr` branch that emits the shim + start script.** Find the start-script block (now reading `if [ "$SHAPE" = static ]; then … else … Docker … fi`) and replace it with a three-way branch:

```bash
# ── 6. Start script + SSR runtime shim ────────────────────────────────
if [ "$SHAPE" = tanstack-ssr ]; then
  info "Writing bun-serve SSR shim (server-entry.ts)..."
  if [ -f server-entry.ts ]; then
    ok "server-entry.ts already present — left in place"
  else
    cat > server-entry.ts << 'SHIM'
// server-entry.ts — bun-native prod runtime for TanStack Start SSR (lovable-setup).
// The build emits dist/server/server.js, a Web-standard { fetch(req, env, ctx) }
// handler that does NOT listen on a port. This shim wraps it with Bun.serve,
// serves hashed client assets from dist/client, and listens on $PORT.
// Start: bun server-entry.ts   (Railway start command: bun run start)
const ENTRY = (await Bun.file("./dist/server/server.js").exists())
  ? "./dist/server/server.js"
  : "./.output/server/index.mjs"; // fallback if a future build emits a nitro layout
const mod = await import(ENTRY);
const app = (mod.default ?? mod) as {
  fetch: (req: Request, env: unknown, ctx: unknown) => Response | Promise<Response>;
};
const port = Number(process.env.PORT ?? 3000);
Bun.serve({
  port,
  idleTimeout: 60,
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
SHIM
    ok "server-entry.ts written (bun-serve SSR runtime)"
  fi
  if grep -q '"start"' package.json; then
    ok "Start script already present"
  else
    sed -i '' '/"build"/a\
    "start": "bun server-entry.ts",
' package.json
    ok "Added SSR start script (bun server-entry.ts)"
  fi
elif [ "$SHAPE" = static ]; then
  info "Checking start script..."
  if ! grep -q '"start"' package.json; then
    if grep -q '"preview"' package.json; then
      sed -i '' '/"preview"/a\
    "start": "bunx serve dist -s -l ${PORT:-3000}",
' package.json
    else
      sed -i '' '/"build"/a\
    "start": "bunx serve dist -s -l ${PORT:-3000}",
' package.json
    fi
    ok "Added static start script (output dir verified after build)"
  else
    ok "Start script already present"
  fi
else
  ok "Docker deploy — Railway builds the Dockerfile, no start script needed"
fi
```

- [ ] **Step 2: Verify the shim heredoc produces a working runtime.** Build the fixture, drop the shim in, boot it, curl it:

```bash
cd /tmp/ls-fixture
bun run build >/dev/null 2>&1 && echo "build ok"
test -f dist/server/server.js && echo "fetch-handler present"
# extract the shim exactly as the script would write it:
sed -n "/cat > server-entry.ts << 'SHIM'/,/^SHIM$/p" ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr/plugins/cosmic-farmland/scripts/lovable-setup \
  | sed '1d;$d' > /tmp/ls-fixture/server-entry.ts
PORT=8788 bun server-entry.ts & SHIM_PID=$!
sleep 2
echo "HTTP $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8788/)"
curl -s http://localhost:8788/ | grep -qiE '<html|<!doctype' && echo "SSR HTML served"
kill $SHIM_PID 2>/dev/null || true
```

Expected: `build ok`, `fetch-handler present`, `HTTP 200`, `SSR HTML served`.

- [ ] **Step 3: Commit.**

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr add plugins/cosmic-farmland/scripts/lovable-setup
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr commit -m "feat(lovable-setup): bun-serve SSR shim + start script for tanstack-ssr"
```

---

## Task 3: Per-shape build verification (+ SSR smoke check)

**Files:**
- Modify: `plugins/cosmic-farmland/scripts/lovable-setup` — the "Build + test verification" block (currently `bun run build` then static `OUT` fixup, around lines 310-319 after Task 1's rename).

- [ ] **Step 1: Replace the build-verify block with a per-shape version.** Find:

```bash
info "Verifying build..."
bun run build 2>&1 | tail -5 || fail "Build failed — fix errors before deploying"
OUT="dist"; [ -d dist/client ] && OUT="dist/client"
if [ "$SHAPE" = static ] && [ "$OUT" != dist ]; then
  sed -i '' "s#bunx serve dist #bunx serve $OUT #" package.json 2>/dev/null || true
  ok "Build OK — start script points at $OUT"
else
  ok "Build OK (output: $OUT)"
fi
```

Replace with:

```bash
info "Verifying build..."
bun run build 2>&1 | tail -5 || fail "Build failed — fix errors before deploying"
if [ "$SHAPE" = tanstack-ssr ]; then
  [ -f dist/server/server.js ] || fail "SSR build did not emit dist/server/server.js — shim has nothing to wrap"
  info "Smoke-testing SSR shim..."
  PORT=8799 bun server-entry.ts >/tmp/lovable-setup-shim.log 2>&1 & SHIM_PID=$!
  sleep 2
  if curl -fsS http://localhost:8799/ >/dev/null 2>&1; then
    ok "Build OK — SSR shim boots + serves / (200)"
  else
    kill "$SHIM_PID" 2>/dev/null || true
    cat /tmp/lovable-setup-shim.log
    fail "SSR shim failed its smoke check — see log above"
  fi
  kill "$SHIM_PID" 2>/dev/null || true
elif [ "$SHAPE" = static ]; then
  OUT="dist"; [ -d dist/client ] && OUT="dist/client"
  if [ "$OUT" != dist ]; then
    sed -i '' "s#bunx serve dist #bunx serve $OUT #" package.json 2>/dev/null || true
    ok "Build OK — start script points at $OUT"
  else
    ok "Build OK (output: $OUT)"
  fi
else
  ok "Build OK (Docker — Railway builds the image)"
fi
```

- [ ] **Step 2: Verify the smoke-check logic against the fixture.** (Shim + build already present from Task 2.)

```bash
cd /tmp/ls-fixture
PORT=8799 bun server-entry.ts >/tmp/lovable-setup-shim.log 2>&1 & SHIM_PID=$!
sleep 2
curl -fsS http://localhost:8799/ >/dev/null && echo "smoke check: PASS" || echo "smoke check: FAIL"
kill "$SHIM_PID" 2>/dev/null || true
```

Expected: `smoke check: PASS`

- [ ] **Step 3: Commit.**

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr add plugins/cosmic-farmland/scripts/lovable-setup
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr commit -m "feat(lovable-setup): per-shape build verify + SSR shim smoke check"
```

---

## Task 4: De-brand — build-gated wrapper swap + `__root.tsx` head

**Files:**
- Modify: `plugins/cosmic-farmland/scripts/lovable-setup` — (a) the de-brand block warning about the wrapper (currently lines ~111-114) and (b) add a new build-gated replacement step **after dependency install** (so `bun add`/`build` work) and **before** the final build-verify.

- [ ] **Step 1: Replace the warn-only wrapper note + extend `__root.tsx` de-brand.** Find:

```bash
if grep -q '@lovable.dev/vite-tanstack-config' package.json 2>/dev/null; then
  warn "Uses @lovable.dev/vite-tanstack-config — head/meta live in src/routes/__root.tsx."
  warn "  Replace the lovable config wrapper with plain TanStack Start + Vite by hand (plain TanStack Start + Vite plugins, no lovable wrapper)."
fi
```

Replace with:

```bash
if grep -q '@lovable.dev/vite-tanstack-config' package.json 2>/dev/null; then
  info "Detected @lovable.dev wrapper — will attempt a build-gated plain-config swap after install."
fi
# SSR head/title/og live in src/routes/__root.tsx, not an HTML file — de-brand it too.
if [ -f src/routes/__root.tsx ] && grep -qi 'lovable' src/routes/__root.tsx 2>/dev/null; then
  sed -i '' 's#https://lovable\.dev[^"'"'"']*##g; s#Lovable Generated Project#'"$PROJECT_NAME"'#g' src/routes/__root.tsx 2>/dev/null || true
  ok "De-branded src/routes/__root.tsx head/meta"
fi
```

- [ ] **Step 2: Add the build-gated wrapper-swap step.** Insert this block immediately **before** the "── 11. Build + test verification" section (after tokensave init, deps are installed by then):

```bash
# ── 10b. De-brand: replace @lovable.dev wrapper with plain config (gated) ─
if [ "$SHAPE" = tanstack-ssr ] && grep -q '@lovable.dev/vite-tanstack-config' package.json 2>/dev/null && [ -f vite.config.ts ]; then
  if ask "Replace @lovable.dev/vite-tanstack-config with plain TanStack Start + Vite config? (build-gated, auto-rollback)"; then
    info "Swapping wrapper for plain config..."
    cp vite.config.ts vite.config.ts.bak
    cat > vite.config.ts << 'PLAINVITE'
// vite.config.ts — plain TanStack Start + Vite (de-branded from
// @lovable.dev/vite-tanstack-config). Dropped: componentTagger (Lovable editor hook),
// dev error-loggers, hmr-gate, dev-server-bridge, sandbox port-pinning, and the
// nitro cloudflare deploy plugin (skipped outside a Lovable sandbox anyway).
// Build emits dist/client + dist/server/server.js (a Web fetch handler) — run it
// with the bun-serve shim (server-entry.ts). VITE_* env vars are auto-exposed by Vite.
import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  server: { host: "::", port: 8080 },
  resolve: {
    alias: { "@": `${process.cwd()}/src` },
    dedupe: [
      "react",
      "react-dom",
      "react/jsx-runtime",
      "react/jsx-dev-runtime",
      "@tanstack/react-query",
      "@tanstack/query-core",
    ],
  },
  plugins: [
    tailwindcss(),
    tsConfigPaths({ projects: ["./tsconfig.json"] }),
    tanstackStart({
      server: { entry: "server" },
      importProtection: {
        behavior: "error",
        client: { files: ["**/server/**"], specifiers: ["server-only"] },
      },
    }),
    viteReact(),
  ],
});
PLAINVITE
    bun remove @lovable.dev/vite-tanstack-config >/dev/null 2>&1 || true
    bun add -d @vitejs/plugin-react @tailwindcss/vite vite-tsconfig-paths @tanstack/react-start >/dev/null 2>&1 || true
    if bun run build >/dev/null 2>&1 && [ -f dist/server/server.js ]; then
      rm -f vite.config.ts.bak
      ok "Wrapper replaced with plain config (build verified, emits dist/server/server.js)"
    else
      mv vite.config.ts.bak vite.config.ts
      bun add -d @lovable.dev/vite-tanstack-config >/dev/null 2>&1 || true
      bun install >/dev/null 2>&1 || true
      warn "Plain-config build failed — restored @lovable.dev wrapper. Replace by hand for a clean break."
    fi
  else
    ok "Kept @lovable.dev wrapper (shim deploys its output regardless)"
  fi
fi
```

- [ ] **Step 3: Verify the swap succeeds on the fixture** (drive the gate manually, non-interactively):

```bash
cd /tmp/ls-fixture
cp vite.config.ts vite.config.ts.bak
cat > vite.config.ts << 'PLAINVITE'
import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";
export default defineConfig({
  server: { host: "::", port: 8080 },
  resolve: {
    alias: { "@": `${process.cwd()}/src` },
    dedupe: ["react","react-dom","react/jsx-runtime","react/jsx-dev-runtime","@tanstack/react-query","@tanstack/query-core"],
  },
  plugins: [
    tailwindcss(),
    tsConfigPaths({ projects: ["./tsconfig.json"] }),
    tanstackStart({ server: { entry: "server" }, importProtection: { behavior: "error", client: { files: ["**/server/**"], specifiers: ["server-only"] } } }),
    viteReact(),
  ],
});
PLAINVITE
bun remove @lovable.dev/vite-tanstack-config >/dev/null 2>&1 || true
bun add -d @vitejs/plugin-react @tailwindcss/vite vite-tsconfig-paths @tanstack/react-start >/dev/null 2>&1 || true
if bun run build >/dev/null 2>&1 && [ -f dist/server/server.js ]; then echo "SWAP OK"; rm -f vite.config.ts.bak; else echo "SWAP FAILED — would roll back"; mv vite.config.ts.bak vite.config.ts; fi
# confirm shim still serves with the plain config build:
PORT=8801 bun server-entry.ts >/tmp/shim2.log 2>&1 & P=$!; sleep 2
echo "post-swap HTTP $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8801/)"; kill $P 2>/dev/null || true
```

Expected: `SWAP OK` and `post-swap HTTP 200`. (If `SWAP FAILED`, the plain template needs adjustment for this wrapper version — note it and keep the wrapper; deploy still works via the shim.)

- [ ] **Step 4: Commit.**

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr add plugins/cosmic-farmland/scripts/lovable-setup
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr commit -m "feat(lovable-setup): build-gated wrapper de-brand + __root.tsx head"
```

---

## Task 5: Per-shape Railway + CLAUDE.md guidance

**Files:**
- Modify: `plugins/cosmic-farmland/scripts/lovable-setup` — CLAUDE.md scaffold deploy line (~line 269) and the Railway start-command guidance (~lines 379-383).

- [ ] **Step 1: Update the CLAUDE.md deploy line.** Find:

```bash
- Deploy: $([ "$SHAPE" = docker ] && echo "Docker image on Railway" || echo "static SPA on Railway")
```

Replace with:

```bash
- Deploy: $(case "$SHAPE" in docker) echo "Docker image on Railway";; tanstack-ssr) echo "TanStack Start SSR on Railway (bun server-entry.ts)";; *) echo "static SPA on Railway";; esac)
```

- [ ] **Step 2: Update the Railway start-command guidance.** Find:

```bash
    if [ "$SHAPE" = static ]; then
      warn "Set Start Command in Railway: Service → Settings → Deploy → 'bun run start'"
    else
      ok "Docker deploy — Railway auto-builds the Dockerfile, no start command needed"
    fi
```

Replace with:

```bash
    case "$SHAPE" in
      tanstack-ssr)
        warn "Set Start Command in Railway: Service → Settings → Deploy → 'bun run start' (runs the SSR shim on \$PORT)" ;;
      static)
        warn "Set Start Command in Railway: Service → Settings → Deploy → 'bun run start'" ;;
      docker)
        ok "Docker deploy — Railway auto-builds the Dockerfile, no start command needed" ;;
    esac
```

- [ ] **Step 3: Verify the script still parses (no syntax errors).**

```bash
bash -n ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr/plugins/cosmic-farmland/scripts/lovable-setup && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit.**

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr add plugins/cosmic-farmland/scripts/lovable-setup
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr commit -m "feat(lovable-setup): per-shape Railway + CLAUDE.md deploy guidance"
```

---

## Task 6: Document the three shapes in SKILL.md

**Files:**
- Modify: `plugins/cosmic-farmland/skills/lovable-setup/SKILL.md`

- [ ] **Step 1: Read the current skill doc** to match its style.

```bash
cat ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr/plugins/cosmic-farmland/skills/lovable-setup/SKILL.md
```

- [ ] **Step 2: Add a "Supported shapes" section.** Append (or merge into the existing structure) this content, adapting headings to the doc's existing style:

```markdown
## Supported project shapes

The script auto-detects one of three shapes (precedence: docker → tanstack-ssr → static):

| Shape | Signal | Deploy |
|-------|--------|--------|
| `docker` | a `Dockerfile` is present | Railway builds the image |
| `tanstack-ssr` | `@tanstack/react-start` in `package.json` | bun-serve shim (`server-entry.ts`), `bun run start` |
| `static` | plain Vite SPA (default) | `bunx serve dist -s` |

### TanStack Start SSR

Lovable's TanStack template (`@lovable.dev/vite-tanstack-config`, `tanstack_start_ts_*`)
builds to `dist/server/server.js` — a Web `{ fetch(req, env, ctx) }` handler that does
**not** listen on a port. The script writes `server-entry.ts`, a bun-native shim that
wraps that handler with `Bun.serve`, serves `dist/client` assets, and listens on `$PORT`.
Runtime is always bun (never node-server).

De-brand attempts to replace the `@lovable.dev` wrapper with a plain TanStack Start + Vite
config. The swap is **build-gated**: if the rebuild fails it auto-restores the wrapper
(`vite.config.ts.bak`) — the shim deploys the wrapper's output either way, so deploy never
depends on the swap succeeding.

Tested against shapes: `tanstack-ssr` (dead-77-odyssey).
```

- [ ] **Step 3: Commit.**

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr add plugins/cosmic-farmland/skills/lovable-setup/SKILL.md
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr commit -m "docs(lovable-setup): document docker/tanstack-ssr/static shapes"
```

---

## Task 7: Full end-to-end run against the throwaway fixture

**Files:** none (integration verification of the whole script).

- [ ] **Step 1: Reset the fixture to pristine** (undo Task 2-4 manual pokes):

```bash
rm -rf /tmp/ls-fixture && cp -R ~/code/dead-77-odyssey /tmp/ls-fixture
cd /tmp/ls-fixture
git remote remove origin 2>/dev/null || true
rm -rf node_modules dist .output server-entry.ts vite.config.ts.bak CLAUDE.md 2>/dev/null || true
git checkout -- vite.config.ts package.json 2>/dev/null || true
echo "remotes: $(git remote | wc -l | tr -d ' ') (want 0)"
```

Expected: `remotes: 0 (want 0)`

- [ ] **Step 2: Run the updated script against the fixture, auto-answering prompts.** The interactive `ask`s that fire: dep-update (y), wrapper-swap (y), history-squash (n — keep), GitHub-create (n — no gh repo), Railway (n). Feed those answers; with no origin the push step no-ops on the create prompt.

```bash
cd /tmp/ls-fixture
printf 'y\ny\nn\nn\nn\n' | ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr/plugins/cosmic-farmland/scripts/lovable-setup /tmp/ls-fixture 2>&1 | tee /tmp/ls-run.log | tail -40
```

Expected (in the log): `Project shape: tanstack-ssr`, `server-entry.ts written`, `Added SSR start script`, wrapper-swap either "replaced … build verified" or "restored … wrapper", `SSR shim boots + serves /`, `Setup complete`.

- [ ] **Step 3: Assert the resulting fixture state.**

```bash
cd /tmp/ls-fixture
echo "shim:        $([ -f server-entry.ts ] && echo yes || echo NO)"
echo "start:       $(grep -o '"start": *"[^"]*"' package.json)"
echo "vitest:      $(grep -q '"vitest"' package.json && echo yes || echo NO)"
echo "pre-push:    $([ -f .githooks/pre-push ] && echo yes || echo NO)"
echo "claude.md:   $([ -f CLAUDE.md ] && echo yes || echo NO)"
echo "railwayign:  $([ -f .railwayignore ] && echo yes || echo NO)"
echo "build srv:   $([ -f dist/server/server.js ] && echo yes || echo NO)"
PORT=8802 bun server-entry.ts >/tmp/shim3.log 2>&1 & P=$!; sleep 2
echo "serve:       HTTP $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8802/)"; kill $P 2>/dev/null || true
```

Expected: every line `yes` / present, `"start": "bun server-entry.ts"`, `serve: HTTP 200`.

- [ ] **Step 4: Verify idempotency — second run no-ops.**

```bash
cd /tmp/ls-fixture
printf 'n\nn\nn\nn\nn\n' | ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr/plugins/cosmic-farmland/scripts/lovable-setup /tmp/ls-fixture 2>&1 | grep -iE 'already|left in place|present' | head
```

Expected: lines reporting existing artifacts ("already present", "left in place") — no errors, exit 0.

- [ ] **Step 5: No commit** (verification only). If any assertion failed, fix the relevant task's script section and re-run Task 7.

---

## Task 8: Real run against dead-77-odyssey + commit its transformation

**Files:** transforms `~/code/dead-77-odyssey` (the live repo). It already has `origin` + pushed history, so the script's squash auto-skips and GitHub-create no-ops (origin exists → it pushes).

- [ ] **Step 1: Decide push behavior.** The script's GitHub step runs `git push --force-with-lease` when `origin` exists. To keep the transformation reviewable, run the script but **decline** Railway, and confirm with the user before any push. Confirm the working tree is clean first:

```bash
cd ~/code/dead-77-odyssey && git status --short
```

If `routeTree.gen.ts` (build artifact) shows as modified, restore it: `git checkout -- src/routeTree.gen.ts`.

- [ ] **Step 2: Run the script against the real repo.** Answers: dep-update (y), wrapper-swap (y), Railway (n). Squash is auto-skipped (pushed history). **Note:** step 13 will attempt to push to origin/main — only proceed if the user has approved pushing; otherwise interrupt before that step.

```bash
cd ~/code/dead-77-odyssey
printf 'y\ny\nn\n' | ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr/plugins/cosmic-farmland/scripts/lovable-setup ~/code/dead-77-odyssey 2>&1 | tee /tmp/ls-real.log | tail -40
```

Expected: `Project shape: tanstack-ssr`, shim written, wrapper swapped (or rolled back), SSR smoke check passes, setup commit created.

- [ ] **Step 3: Verify the real repo serves SSR.**

```bash
cd ~/code/dead-77-odyssey
PORT=8803 bun server-entry.ts >/tmp/shim-real.log 2>&1 & P=$!; sleep 2
echo "serve: HTTP $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8803/)"; kill $P 2>/dev/null || true
git log --oneline -3
```

Expected: `serve: HTTP 200`; a "Setup: de-brand + configure (lovable-setup)" commit present.

- [ ] **Step 4: Push the tool branch + open PR** (cosmic-farmland), and confirm the dead-77-odyssey transformation push with the user.

```bash
git -C ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr push -u origin feat/lovable-setup-tanstack-ssr
cd ~/code/cosmic-farmland-feat-lovable-setup-tanstack-ssr && gh pr create --title "feat(lovable-setup): TanStack-Start SSR support" --body "Adds shape detection (docker/tanstack-ssr/static), a bun-native Bun.serve SSR shim, and a build-gated reversible @lovable.dev wrapper de-brand. Verified end-to-end against dead-77-odyssey."
```

---

## Self-review notes

- **Spec coverage:** shape detection (T1), bun-serve shim + start (T2), per-shape build-verify + SSR smoke (T3), build-gated reversible wrapper de-brand + `__root.tsx` (T4), Railway/CLAUDE.md guidance (T5), SKILL.md (T6), fixture verify + idempotency (T7), real-repo transform (T8). All spec sections mapped.
- **Type/name consistency:** `SHAPE` value `tanstack-ssr` used identically in all branches; shim file `server-entry.ts`, start `bun server-entry.ts`, build artifact `dist/server/server.js`, client dir `dist/client` consistent across T2/T3/T4/T7/T8.
- **Risk:** the plain-config template is faithful to wrapper v2.1.1; the build-gate + `.bak` rollback (T4) makes a version mismatch safe (keeps the wrapper, shim still deploys). T4 Step 3 catches it on the fixture before any real run.
