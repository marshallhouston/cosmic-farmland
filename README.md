# cosmic-farmland

> **Warning:** This isn't ready for primetime and should not be relied on for stability. I will change and break these unexpectedly.

Cross-project scripts and a Claude Code plugin for my dev workflow.

- `bin/` — standalone shell scripts
- `plugins/marshall-tools/` — Claude Code plugin with skills, commands, and hooks
- `plugins/obsidian-weaver/` — Claude Code plugin: Obsidian vault interface + auto-weaving knowledge graph

## Install

In Claude Code:

```
/plugin marketplace add marshallhouston/cosmic-farmland
/plugin install marshall-tools@cosmic-farmland
/plugin install obsidian-weaver@cosmic-farmland
/reload-plugins
```

Install whichever you want. See each plugin's README for usage:

- [plugins/marshall-tools/README.md](plugins/marshall-tools/README.md)
- [plugins/obsidian-weaver/README.md](plugins/obsidian-weaver/README.md)
