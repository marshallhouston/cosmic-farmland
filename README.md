# cosmic-farmland

> **Warning:** This isn't ready for primetime and should not be relied on for stability. I will change and break these unexpectedly.

Cross-project scripts and a Claude Code plugin for my dev workflow.

- `bin/` — standalone shell scripts
- `plugins/cosmic-farmland/` — Claude Code plugin with skills, commands, and hooks
- `plugins/obsidian-weaver/` — Claude Code plugin: Obsidian vault interface + auto-weaving knowledge graph

## Install

In Claude Code:

```
/plugin marketplace add marshallhouston/cosmic-farmland
/plugin install cosmic-farmland@cosmic-farmland
/plugin install obsidian-weaver@cosmic-farmland
/reload-plugins
```

Install whichever you want. See each plugin's README for usage:

- [plugins/cosmic-farmland/README.md](plugins/cosmic-farmland/README.md)
- [plugins/obsidian-weaver/README.md](plugins/obsidian-weaver/README.md)

## Development

### One-time setup

Wire the repo's hooks (pre-commit blocks per-commit drift, pre-push runs the CI version-gate against `origin/main` so you catch cumulative branch drift before pushing):

```
bash scripts/setup-hooks.sh
```

Plugin caches key off the `version` field. Edits that ship without a bump silently keep consumers on the old code.

### Editing a plugin

When you change anything under `plugins/<name>/` you must also bump `plugins/<name>/plugin.json` `"version"` in the same commit. Semver:

- **patch** (`x.y.Z`) -- bug fixes, prose tweaks, internal refactors
- **minor** (`x.Y.0`) -- new commands / skills / hooks, new behavior
- **major** (`X.0.0`) -- removed or renamed commands, breaking config

The pre-commit hook (above) enforces this. If you see `ERROR: plugins/... changed without bumping ...`, edit the listed `plugin.json`, stage it, and re-commit.
