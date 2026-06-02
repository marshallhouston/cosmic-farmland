<!-- lovable-setup:conventions — maintained in cosmic-farmland/templates/claude-md-tail.md, edit there -->
## Working conventions

Global rules in `~/.claude/CLAUDE.md` apply here too (they auto-load — not repeated per-project):
worktrees for isolated work · **no wall-clock time estimates** (complexity + decomposition only) ·
RTK token-proxy + caveman mode · memory discipline (`/systematize` over saving) · BFF (Build-Friction-Fix, bias to action).

**Code exploration:** `tokensave_*` tools / `.tokensave/tokensave.db` when `.tokensave/` exists — not Explore agents. `/graphify` for input → knowledge graph.

**Dev process (superpowers):** brainstorm before building · TDD (red-green-refactor) · `systematic-debugging` for any bug · `writing-plans` → `/execute-plan` for multi-step work · request/receive code review before merge · verify before claiming done.

**Visual (visual-explainer):** `/generate-web-diagram`, `/plan-review`, `/diff-review`, `/project-recap` instead of dumping big ASCII tables.

**Workflow (cosmic-farmland):**
- `/next` — what to work on next        · `/ship` — green-merge PR, clean up worktree + branch
- `/ptv` `/ptvm` — bloat audit pre-merge · `/ptv-idea` — PTV a proposal before code
- `/grill-me` `/grill-with-docs` — stress-test a plan · `/triage` `/feedback-triage` — bugs/feedback → issues
- `/handoff` — fresh-session resumption prompt · `/wrap` — end-of-session cap · `/systematize` — promote a lesson to enforcement

## Testing

- **Stack:** Vitest + Testing Library (jsdom).
- **Run:** `bun run test` (watch: `bun run test:watch`).
- **Required before commit/merge.** Keep the smoke test green; add tests alongside features.
- **Deploy gate:** `.githooks/pre-push` runs the suite on every push to `main` and blocks the push if it fails (activate once: `git config core.hooksPath .githooks`; worktrees inherit it). Bypass non-code pushes with `git push --no-verify`.

## Design + formatting

- **Design system:** `design.html` (repo root) is the living style guide — palette, type scale, spacing, and a component gallery generated from the real styles at setup. Regenerate it when the visual language changes.
- **Formatting:** `bun run format` (prettier). The scaffold is formatted once at setup; keep it clean — format before committing.
