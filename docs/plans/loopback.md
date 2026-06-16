# loopback (was: feedback-bridge / bridge)

> **Status (2026-06-16): partially superseded, not built.** Goal (a) — kill copy-paste friction in `feedback` skill — already solved by `contextbridge open` (commit afc9ab5; HTML+paste kept as fallback). Goal (b) — a standalone generalized `loopback`/`bridge` CLI reusable across skills — **unbuilt**. Original pain gone; only the generalization remains, and it needs a fresh value-prove before any code. Not shovel-ready.

Dogfood-driven exploration: build a contextbridge-shaped CLI in cosmic-farmland that powers human-in-loop review for multiple skills via swappable UI templates. Goal is both (a) eliminate manual copy-paste friction in the current `feedback` skill and (b) learn contextbridge's architecture by reimplementing the transport, generalized.

## Why

Current `feedback` skill flow:
1. Generate `feedback.html`
2. `open feedback.html`
3. User fills sections, clicks "Copy All Feedback as markdown"
4. User **manually pastes** into Claude Code chat
5. Skill applies feedback per section

Step 4 is the friction. contextbridge has solved this for plan review via stdin/stdout transport: CLI holds a local HTTP server, blocks until submit, prints markdown to stdout, exits. Stdout lands in Claude's tool result naturally.

Same trick generalizes to any "review-then-respond" skill.

## Two options on the table

### Option A: use `contextbridge open` directly
- Zero new code
- Inline annotation UI (proven: dogfooded on this very plan; annotations were clear and per-section)
- Cheapest test of whether bespoke UI earns its place

### Option B: build a generic `loopback` CLI in cosmic-farmland
- One binary, multiple UI templates
- Reuse contextbridge's transport pattern (server + submit + stdout + exit)
- Each new "review style" = new template directory, NOT new binary
- Teaches transport pattern hands-on

This plan now covers a generalized Option B. Option A remains the precondition test.

## Phase 0: precondition test (Option A first)

Before building anything:

1. Pick a real review target
2. Run `contextbridge open <file>` instead of the current HTML generator
3. Annotate as you normally would
4. Assess: inline annotation vs. per-section textareas -- does Option A degrade applied-feedback quality?

Exit criteria:
- If A sufficient -> rewire `feedback` skill to call `contextbridge open` and stop
- If A loses critical structure -> proceed to Phase 1

(Dogfooding update: this plan was itself reviewed via `contextbridge open`. Inline highlight-to-comment captured per-section feedback fine. Strong signal A may be enough for most cases.)

## Phase 1: generic `loopback` CLI

Location: `~/code/cosmic-farmland/bin/loopback` (committed to the cosmic-farmland repo; PATH already wired per CLAUDE.md)

Runtime: Bun. Surface:

```
loopback --ui <template> <file-path>
  Reads file, serves the chosen template on localhost, opens browser,
  blocks until submit, prints markdown feedback to stdout, exits.

loopback --ui feedback   <file>   # three-panel section review (current feedback skill UI)
loopback --ui review     <file>   # checklist-style review (future)
loopback --ui interview  <file>   # grill-me style prompts (future)
loopback --port <n>               # override default port
loopback --no-open                # skip auto-opening browser
loopback --list-uis               # show available templates
```

Internal architecture (mirrors contextloopback core):

1. Parse args, read file, load template from `bin/loopback/templates/<name>/`
2. `Bun.serve` on ephemeral port; template = `index.html` + optional `app.js` + `style.css`
3. Route `GET /`            -> template HTML with `{{CONTENT}}` substituted
4. Route `GET /content.json` -> raw file content as JSON (templates pull this client-side if they prefer)
5. Route `POST /submit`     -> body `{markdown: string}`; write to stdout; `process.exit(0)`
6. Route `POST /cancel`     -> exit non-zero, no stdout
7. `open http://localhost:<port>` (skippable)
8. Block until exit

Bonus: templates are pure static-asset directories. Add a new review style = drop a folder in `templates/`. No CLI changes.

## Phase 2: skill rewire (additive, not destructive)

Update `plugins/cosmic-farmland/skills/feedback/SKILL.md` to **auto-detect**:

```bash
if command -v loopback >/dev/null 2>&1; then
  loopback --ui feedback "<file-path>"
else
  # fallback: existing HTML generator + manual paste
  bundle exec ruby _scripts/generate-feedback-html "<file-path>"
  open feedback.html
  # wait for paste
fi
```

Both paths coexist. New path takes over silently once `loopback` is on PATH. Old path keeps machines without the binary working. Zero choice burden on the user.

Future skills (`/review`, `/grill-me`, etc.) follow the same auto-detect pattern.

## Phase 3: distribution

- Local: `bun build --compile ./bin/loopback.ts --outfile ./bin/loopback` (or skip compile and run via `bun run` shebang)
- PATH: cosmic-farmland's `bin/` already on PATH (verify via `which lovable-setup`)
- Templates ship in-repo at `bin/loopback/templates/`
- Public distribution / open source: only if the pattern generalizes beyond marshall's machine. Defer.

## Phase 4: template catalogue

Once `loopback --ui feedback` works, add templates per need. NOT new CLIs:

- `templates/feedback/`  three-panel section review (Phase 1 target)
- `templates/review/`    PR-review checklist + per-file comments
- `templates/interview/` grill-me question/answer capture
- `templates/triage/`    feedback-triage rubric (accept/defer/kill per item)

Each = HTML + JS + CSS in its own folder. Maybe 50-200 lines each. Shared transport from `loopback` core.

## Open questions

1. Does Phase 0 obviate Phase 1 for the `feedback` skill specifically? Run it on a real document, then decide.
2. Bun.serve compile vs. shebang script: pick whichever is lowest-friction for marshall's PATH setup.
3. Multi-file annotation: contextbridge open doesn't do it. Should `loopback` templates support it? Defer until a real skill needs it.
4. Naming: settled on `loopback` (network-roundtrip semantics; no collision with `contextbridge`). Other candidates were `roundtrip`, `parley`, `huddle`.

## PTV verdict

N/A -- exploration/learning, not a preach-hub product change. Cosmic-farmland is the tooling repo; the gate is "does this remove real friction in marshall's actual workflow?" Phase 0 answers that.

## Success criteria

- Phase 0: clear yes/no on whether bespoke UI earns its place for `feedback` skill
- Phase 1 (if reached): one full feedback cycle on a real document with zero manual paste, via `loopback --ui feedback`
- Phase 2 (if reached): `feedback` skill auto-detects and uses new path when available, falls back when not
- Phase 4 (stretch): at least one additional template proves the swap-template-not-binary model

---

## Phase 0 result (2026-05-21)

PASS. Dogfooded `contextbridge open` on `~/code/preach-hub/docs/brainstorms/2026-05-20-graphify-cards-schema.md`. Inline annotation captured 1 general + 2 line-specific comments with full fidelity. All three were applied to the brainstorm doc without paste friction.

**Verdict:** Option A sufficient for `feedback` skill in the common case. Skip Phase 1 build.

**Action taken:** Updated `plugins/cosmic-farmland/skills/feedback/SKILL.md` to auto-detect `contextbridge open` and fall back to the existing HTML+paste flow when the binary is unavailable. Both paths coexist.

**Re-open trigger:** If a future skill genuinely requires section textareas (e.g., a rubric-driven review where each section has structured fields rather than free annotation), revisit Phase 1 with the generic `loopback` CLI design preserved above.
