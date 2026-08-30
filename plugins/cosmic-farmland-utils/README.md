# cosmic-farmland-utils

Personal utilities: tee times, activity and skill stats, disk cleanup, screenshots, cosmicfarmland.wtf deploys, Lovable setup.

Split out of `cosmic-farmland` in 4.0.0 so the always-on context cost matches how often each skill fires. These are on-demand, not part of the daily dev loop. Install it and leave it disabled until you need it: a disabled plugin costs zero tokens, but its skills cannot fire until enabled plus a restart.

## Install

```
/plugin marketplace add marshallhouston/cosmic-farmland
/plugin install cosmic-farmland-utils@cosmic-farmland
/plugin enable cosmic-farmland-utils@cosmic-farmland
/reload-plugins
```

Disable when done: `/plugin disable cosmic-farmland-utils@cosmic-farmland`.

## Contents

**Skills**

- `activity-stats` - wall-clock hours worked on this repo, from git commits plus Claude session events. `[author-substring] [tz]`, defaults `marshall` / `America/Denver`
- `cf-deploy` - provision `<name>.cosmicfarmland.wtf` end to end: repo, Railway service and domain, Cloudflare CNAME, live verify
- `disk-memory-cleanup` - free disk space: run the cleanup script, then hunt new space hogs
- `golf-tee-times` - tee times across 11 Denver courses, filtered by date, players, time, holes
- `screenshot` - read the newest screenshot(s) and act on the intent given. `/screenshot [N] [intent]`. Folder auto-resolves via `defaults read com.apple.screencapture location` (macOS); override with `SCREENSHOT_DIR=/path`. Capture-then-invoke only, it does not take screenshots for you
- `skill-stats` - skill-usage report from session transcripts, every project, all history. Finds dead skills worth pruning

**Commands**

- `/lovable-setup [project-dir]` - take a freshly exported Lovable app to a real dev setup: de-brand, deps, lint, tests, design.html, favicon and social preview, deploy scaffolding

## Notes

`scripts/lovable-setup` is also exposed as a standalone CLI: the repo's `bin/lovable-setup` symlinks to it, and `bash bin/install.sh` puts it on your PATH. It reads `templates/claude-md-tail.md` relative to its own path, so the script and templates must move together.

Bare command names only resolve if a shadow exists in `~/.claude/commands/`. Otherwise use the namespaced form: `/cosmic-farmland-utils:lovable-setup`.
