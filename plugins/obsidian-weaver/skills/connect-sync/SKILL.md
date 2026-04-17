---
name: connect-sync
description: "Sync recent Obsidian notes into the _connections/ knowledge graph. Scans modified files for themes, people, concerns, and decisions, then updates connection pages with new source links. Use when the user says 'sync connections', 'connect-sync', 'update connections', 'sync my notes', or after meetings to keep the knowledge graph current. Also invoked automatically by scheduled triggers."
args: "[today | file <path> | deep | since <date>]"
---

# /connect-sync — Connection Sync

Incrementally updates the `_connections/` knowledge graph by scanning recently modified Obsidian notes for mentions of known themes, people, concerns, and decisions. Keeps connection pages current without re-running the full vault analysis.

## Modes

- **Default** (no args): Sync all files modified since last sync
- **`today`**: Sync all files modified today
- **`file <path>`**: Sync a specific note file
- **`deep`**: Full sync with LLM analysis — detects NEW themes, concerns, and decisions not yet in the registry
- **`since <date>`**: Sync files modified since a specific date (YYYY-MM-DD)

## Obsidian CLI Usage (optional)

If the `obsidian` CLI is installed, skills can leverage it for richer vault interaction:

- **Get outgoing links**: `obsidian links file="note-name"` — returns all wikilinks from a note
- **Get backlinks**: `obsidian backlinks file="note-name"` — returns files that link TO a note
- **Search vault**: `obsidian search:context query="text" limit=N` — full-text search with surrounding context
- **Read notes**: `obsidian read file="note-name"` — read by wikilink-style name
- **Append to daily note**: `obsidian daily:append content="## Connection Sync\n..."` — append sync log to today's daily note
- **List tags**: `obsidian tags file="note-name"` — get tags from a specific note

The Python sync script (`connect-sync.py`) handles the bulk pattern matching. The CLI supplements it for deep mode analysis and daily note updates.

## Step 1: Run the Pattern-Matching Sync

Run the Python sync script to handle known-entity matching:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/connect-sync.py" [args based on mode]
```

`CLAUDE_PLUGIN_ROOT` is set automatically by Claude Code. Requires `OBSIDIAN_VAULT` env var pointing at the vault root (set by `/obsidian-setup`).

Arg mapping:
- Default → no args (uses last sync timestamp)
- `today` → `--today`
- `file <path>` → `--file "<path>"`
- `deep` → `--deep --today` (deep always scans today's files, pass `--deep` flag to get LLM review candidates)
- `since <date>` → `--since <date>`

The script outputs JSON. Key fields:
- `files_scanned`, `files_with_updates`, `total_links_added`
- `updates`: array of `{file, note, connections: [{type, name}]}`
- `needs_llm_review` (deep mode only): files the pattern matcher couldn't classify — 0 or 1 hits
- `low_hit_total` (deep mode only): total count of unclassified files

If `status` is `no_changes`, report that and stop (unless mode is `deep`).

## Step 2: Report Results

Summarize what was synced:

```
Synced 5 notes → 12 new links added

- 2026-04-15 1on1 derrick-henry → [[Platform Migration]], [[Hiring Plan]]
- 2026-04-15 team-standup → [[Release Process]], [[Q2 Goals]]
...
```

## Step 3: Deep Mode — LLM Entity Detection (only if mode is `deep`)

The script's `needs_llm_review` array contains files the pattern matcher flagged as unrecognized (0-1 entity hits). These are the files most likely to contain new entities.

**For each file in `needs_llm_review` (up to 30):**

1. Read the full file content
2. Analyze it for:
   - **Themes** discussed that don't match any existing theme in the registry
   - **Concerns** raised that aren't in `_connections/concerns/`
   - **Decisions** made that aren't in `_connections/decisions/`
   - **People** mentioned who don't have a page in `_connections/people/`
3. For any genuinely new entity (not a passing mention — it must have substance):
   - Create a new connection page in the appropriate `_connections/` subfolder using the format of existing pages
   - Add the entity to `_connections/.registry.json` — both the type list and `_alias_map` with reasonable aliases
   - Link the source note to the new connection page
   - Inject backlinks into the source note
   - Use `obsidian links` and `obsidian backlinks` to understand the connection graph for each file, supplementing the LLM analysis
4. **Be conservative** — only create pages for entities that appear in 2+ notes or represent a significant topic. A one-off mention of a tool name is not a theme.

**After creating new entities:**
- Re-run the pattern-matching script (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/connect-sync.py" --today`) so the new aliases get picked up across today's other notes
- The script automatically rebuilds the index when it adds links

## Step 4: Update Daily Note (if one exists for today)

Check if today's daily note exists at `<daily_notes>/YYYY-MM-DD.md`, where `<daily_notes>` is the value from the `Paths` table in the vault's `CLAUDE.md` (fallback `_weekly/_daily/`).

If the `obsidian` CLI is installed, use `obsidian daily:append content="..."` — it handles path resolution natively. Otherwise edit the file directly.

Append a `## Connection Sync` section:

```markdown
## Connection Sync
*Auto-synced at HH:MM*

- Synced N notes, M new links
- Updated: [[Theme1]], [[Person1]], [[Concern1]]
- New entities: [[NewTheme]] (theme), [[NewConcern]] (concern)
```

If the section already exists (from an earlier sync today), update it rather than duplicating.

## State Tracking

- Sync state: `_connections/.sync-state.json`
- Entity registry: `_connections/.registry.json`
- Both updated automatically by the Python script
- Deep mode also updates the registry when it creates new entities
- Index (`_connections/_index.md`) is rebuilt automatically after any sync that adds links

## Scheduled Trigger Integration (optional)

This skill is designed to run on a schedule via Claude Code's cron system. Suggested schedule:

- **9:03am, 12:07pm** — Pattern match only (default mode). Quick and silent.
- **5:13pm** — Deep mode with LLM analysis. Detects new entities from the day's notes.

When invoked by a trigger:
- Run in the specified mode
- If no changes found, exit silently
- If changes found, write the changelog to the daily note
- Keep output concise — triggers run unattended
