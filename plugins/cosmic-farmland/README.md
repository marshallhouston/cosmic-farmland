# cosmic-farmland

Marshall's cross-project skills, commands, and hooks.

## Breaking changes

**4.0.0** - Split into three plugins so the always-on context cost matches how often each skill fires. `cosmic-farmland` keeps the daily dev loop and every hook. Content work (feedback pages, review docs, carousels, Granola sync) moved to `cosmic-farmland-content`; personal utilities (tee times, activity/skill stats, disk cleanup, screenshots, cf-deploy, Lovable setup) moved to `cosmic-farmland-utils`. Install those two and enable when needed: a disabled plugin costs zero tokens, but its skills cannot fire until enabled and a restart.

**2.0.0** - Removed the alias commands `/ptvm`, `/ptvi`, `/prove-the-value-motherfucker`, `/prove-the-value-idea`, and the deprecated `/fart-smell-detection` shim. Every plugin command's description loads into every session, so five aliases for two skills was pure context cost. Canonical names: `/ptv`, `/fart-sniffing-detection`, `/ptv-idea`.

**1.0.0** - `fart-smell-detection` skill/command renamed to `fart-sniffing-detection`. Pin to `0.5.1` if you relied on the old name.

## Install

In Claude Code:

```
/plugin marketplace add marshallhouston/cosmic-farmland
/plugin install cosmic-farmland@cosmic-farmland
/reload-plugins
```

## Contents

**Skills**

- `disk-memory-cleanup` — free disk space (Xcode caches, node_modules, etc.)
- `fart-sniffing-detection` — PTVM ("Prove The Value Motherfucker") audit of recent commits or a PR. Flags cologne-sniffing changes, ranks kill candidates. Four skepticism levels: `whiff` → `sniff` → `huff` → `dutch-oven-yourselff`.
- `ptv-idea` — same PTVM rubric applied to a *proposal* before code exists. Six-dimension audit (premise, value, complexity, alternatives, reversibility, scope creep), verdicts BUILD/TRIM/DEFER/KILL, always names the Smallest Version That Proves The Premise. Same four skepticism levels.
- `feedback` — section-by-section review loop
- `feedback-triage` — intake a raw feedback blob from a named source, triage each item (category/tier/size/decision), write a dated doc, propose worktrees for accepted items
- `golf-tee-times` — check tee time availability
- `handoff` — generate self-contained session handoff
- `interactive-review-doc` — create interactive HTML review docs
- `screenshot` — reads your newest screenshot(s) (up to 10) and executes the intent you give after the count. `/screenshot` explains newest. `/screenshot fix` debugs an error in the image and edits code. `/screenshot 3 make infographic` reads last 3 and produces an infographic. `/screenshot do this` remixes the pattern in the image toward your goals. Folder auto-resolves via `defaults read com.apple.screencapture location` (macOS); override with `SCREENSHOT_DIR=/path`. Capture-then-invoke only; does not take screenshots for you.

**Commands**

- `/execute-plan` — execute a written plan
- `/fart-sniffing-detection [level] [target]` — run the skill above. Target = PR number, git range, `--staged`, or auto-detect current branch's open PR.
- `/ptv-idea [level] <idea>` — PTVM-audit a proposal before code exists (idea text, path to a spec doc, or `last turn`).
- `/feedback-triage <source>` — triage a pasted feedback blob from a named source (runs the `feedback-triage` skill)
- `/granola-sync` — sync recent Granola meetings
- `/ship [pr-number]` — watch a PR's checks, merge when green, clean up worktree + local branch. Defaults to current branch's PR.

## Short-name resolution (`/ptv` returning "Unknown command")

Claude Code resolves plugin commands under their namespaced form: `/cosmic-farmland:<name>`. The bare form (`/ptv`, `/next`, etc.) only resolves if a matching file exists in `~/.claude/commands/` as a **user-global shadow**. No shadow → bare name errors with "Unknown command: /ptv." even after `/plugin update` and `/reload-plugins`.

Two ways to use bare names:

1. **Use the namespaced form** — `/cosmic-farmland:ptv huff`. Always works.
2. **Install a shadow** — copy the plugin command file to `~/.claude/commands/`:
   ```
   cp ~/.claude/plugins/cache/cosmic-farmland/cosmic-farmland/*/commands/ptv.md ~/.claude/commands/ptv.md
   ```
   Then `/reload-plugins`. Shadow is machine-local (not tracked in this repo) and must be re-copied per machine. Shadows drift from the plugin over time — prefer the namespaced form unless muscle memory demands otherwise.
