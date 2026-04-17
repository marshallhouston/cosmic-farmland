# _connections-seed

Copy this folder to `_connections/` inside your Obsidian vault.

```
_connections/
├── .registry.json          # Edit this to list your real entities
├── themes/                 # One page per theme (e.g. "Platform Migration.md")
├── people/                 # One page per person (e.g. "Derrick Henry.md")
├── concerns/               # Ongoing concerns/risks
└── decisions/              # Decisions you've made (with dates)
```

## How the registry works

Every entity has a **canonical name** (what's displayed) and **aliases** (what the script pattern-matches in your notes).

In `.registry.json`:

```json
"_alias_map": {
  "derrick henry": { "type": "person", "canonical": "Derrick Henry" },
  "derrick": { "type": "person", "canonical": "Derrick Henry" }
}
```

Both "Derrick Henry" and "Derrick" in your notes will match to the `people/Derrick Henry.md` page.

**Rules of thumb:**
- Aliases must be 3+ characters (avoid false positives on "AI", "B2B", etc.)
- Longest aliases match first (greedy), so include specific multi-word aliases before short ones
- Case-insensitive

## Starting from scratch

1. Open `.registry.json` and replace the sample entries with your real ones.
2. Create a corresponding `.md` file in the right subfolder for each entity.
3. Run `python3 .claude/scripts/connect-sync.py --today` — it will scan today's notes and link them in.
4. Over time, run with `--deep` to let an LLM discover entities you haven't registered yet.
