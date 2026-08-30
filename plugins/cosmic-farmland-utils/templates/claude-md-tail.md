<!-- lovable-setup:conventions — maintained in cosmic-farmland-utils/templates/claude-md-tail.md, edit there -->
## Working conventions

Global rules in `~/.claude/CLAUDE.md` auto-load here, not repeated per-project.

Workflow commands: `/next` (what to work on), `/ship` (green-merge PR plus cleanup), `/ptv` (bloat audit pre-merge), `/ptv-idea` (audit a proposal before code), `/handoff`, `/wrap`, `/systematize`.

## Testing

- **Stack:** Vitest + Testing Library (jsdom).
- **Run:** `bun run test` (watch: `bun run test:watch`).
- **Required before commit/merge.** Keep the smoke test green; add tests alongside features.
- **Deploy gate:** `.githooks/pre-push` runs the suite on every push to `main` and blocks the push if it fails (activate once: `git config core.hooksPath .githooks`; worktrees inherit it). Bypass non-code pushes with `git push --no-verify`.

## Design + formatting

- **Design system:** `design.html` (repo root) is the living style guide — palette, type scale, spacing, and a component gallery generated from the real styles at setup. Regenerate it when the visual language changes.
- **Formatting:** `bun run format` (prettier). The scaffold is formatted once at setup; keep it clean — format before committing.
