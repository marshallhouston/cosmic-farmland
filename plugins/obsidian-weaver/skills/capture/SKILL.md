---
name: capture
description: "Capture brain dumps, article links, and thoughts into the structured knowledge store. Use when the user says 'capture', '/capture', 'brain dump', 'save this thought', 'save this link', 'capture this', or wants to save an idea, article, or reflection for later use. With 'pull' arg, batch-imports from a Slack self-DM channel (requires Slack MCP)."
args: "[url-or-text | pull]"
---

# /capture — Knowledge Curator

Captures ideas, links, and reflections into `_inbox/captures/` so they become structured, connected knowledge that other skills can read.

Two modes:
- **Manual** (`/capture <url-or-text>`): Capture a thought or article right now
- **Pull** (`/capture pull`): Batch-import substantive messages from a Slack self-DM channel (requires Slack MCP — skip if you don't have it)

## Folder Layout (assumed)

This skill assumes the following folders in your vault:

```
_inbox/
  captures/                # where new captures land
_strategy/                 # one .md file per strategic area (used as tags)
_people/                   # one .md file per person (used for connections)
_projects/                 # one .md file per project (used for connections)
```

Adjust paths in this skill if your vault uses different folder names. Empty folders are fine — the skill will simply have nothing to tag against or connect to.

## Obsidian CLI Usage

If installed:

- `obsidian create path="_inbox/captures/YYYY-MM-DD-slug.md" content="..."` — create the capture file
- `obsidian read file="capture-name"` — read by wikilink-style name
- `obsidian search:context query="text" path="_inbox/captures" limit=N` — find related captures

For complex YAML frontmatter, the standard `Write` tool is often more practical than the CLI's `property:set`.

## Manual Mode

Triggered when `/capture` is given any argument that isn't the word `pull`.

### Step 1: Parse the Input

The argument may be:
- A URL alone
- Freeform text alone (a brain dump)
- A URL with freeform text (the user's thoughts about the link)
- Freeform text with one or more URLs inline

Separate URL(s) from freeform text. At least one must be present.

### Step 2: Fetch URL Content (if applicable)

If a URL was provided, use **WebFetch** to retrieve it. Extract the article title and main body content (skip nav/ads).

If WebFetch fails: note "Could not fetch article content" and continue. The capture still gets created.

### Step 3: Preserve Raw Thoughts

The user's freeform text is their raw thinking. Store it **verbatim** in the capture file. Never summarize, paraphrase, clean up grammar, or reword it. This is sacred.

### Step 4: Extract Takeaways

Generate 2-5 key takeaways from the combined content. These should be:
- Concise bullet points
- Focused on what matters to the user
- Actionable where possible

If the capture is a pure brain dump (no article), takeaways are distilled from the user's own words — but the raw thoughts section preserves everything verbatim.

### Step 5: Tag Strategic Areas

Read the filenames in `<strategy>/` (excluding `.gitkeep` and similar), where `<strategy>` is the value from the `Paths` table in the vault's `CLAUDE.md` (key `strategy`). Each filename minus `.md` is a valid tag.

A capture can have zero, one, or multiple tags. Only tag when there is a genuine connection — do not force tags.

If the folder is empty or missing, skip tagging and note "No strategic areas defined yet."

### Step 6: Find Connections

Resolve `<captures>`, `<people>`, and `<projects>` from the `Paths` table in the vault's `CLAUDE.md`, then scan:

- `<captures>/` — recent captures (read frontmatter and first few lines)
- `<people>/` — check if anyone mentioned is relevant
- `<projects>/` — check if a project relates to this topic

A connection must be genuinely useful. Zero connections is fine. Forced connections erode trust.

Connections are recorded as bare filenames without paths or extensions:

```yaml
connections: [derrick-henry, platform-migration, 2026-04-10-onboarding-thoughts]
```

### Step 7: Write the Capture File

**Filename:** `<captures>/YYYY-MM-DD-<slug>.md`, where `<captures>` is the value from the `Paths` table in the vault's `CLAUDE.md` (fallback `_inbox/captures/`).

**Before writing:** if `$OBSIDIAN_VAULT/<captures>/` doesn't exist, ask the user: *"The folder `<captures>/` doesn't exist in your vault. Create it? [y/n]"*. On `y`, run `mkdir -p "$OBSIDIAN_VAULT/<captures>"` and continue. On `n`, stop and tell them to create the folder or update the `captures` path in `CLAUDE.md`.

Generate the slug from the key topic. Keep it short, lowercase, hyphenated.

If a file with that name exists, append `-2`, `-3`, etc.

**File format:**

```yaml
---
date: YYYY-MM-DD
source: <url or "brain-dump">
strategic_areas: [list of matching strategy slugs, or empty]
connections: [list of related file slugs, or empty]
---
```

Body sections (adapt to content):

- **Raw thoughts** — verbatim user input (always present if they typed anything)
- **Article summary** — brief summary of fetched content (only if URL was fetched)
- **Key takeaways** — the 2-5 distilled points
- **Connections** — brief explanation of why each connection is relevant (only if connections were found)

Use `[[wikilinks]]` when referencing people or other notes. Wikilinks are kebab-case: `[[derrick-henry]]` not `[[Derrick Henry]]`.

### Step 8: Report

Tell the user:
- What was captured (one line)
- Strategic areas it connects to (if any)
- Connections found (if any)
- The file path

Keep the report brief — 3-5 lines max.

## Pull Mode (Optional — requires Slack MCP)

Triggered by `/capture pull`. **Skip this entire section if you don't use Slack or don't have the Slack MCP integration installed.**

### Step 1: Read Configuration

Read `_inbox/.capture-config.json` (or wherever you store it) to get the self-DM channel ID.

```json
{ "self_dm_channel_id": "DXXXXXXXX" }
```

If the config file doesn't exist, ask the user for the channel ID and offer to save it.

### Step 2: Determine Time Window

Read `_inbox/.last-capture-pull` for the last pull timestamp.
- If exists: use as the "since" timestamp
- If not: default to 7 days ago

### Step 3: Fetch Slack Messages

Use the **slack_read_channel** MCP tool with the configured channel ID. Filter to messages since the last pull timestamp.

If Slack MCP is unavailable: display "Slack MCP not configured — pull mode unavailable" and stop. Do not create captures.

### Step 4: Triage Messages

**Substantive (create a capture):**
- Links with thoughts or commentary
- Multi-sentence reflections or ideas
- Questions you're wrestling with
- Reading recommendations with context
- Strategic observations

**Non-substantive (skip):**
- Single-word reactions
- Phone numbers, addresses, logistics
- Memes/images without commentary
- Bare URLs with no thought attached (borderline — if the URL title is clearly substantive, treat as substantive)

### Step 5: Create Captures

For each substantive message, follow Manual Mode Steps 4-7. Use the message timestamp for the date in the filename.

### Step 6: Update Last Pull Timestamp

Write the current ISO 8601 timestamp to `_inbox/.last-capture-pull`. Do this even if no substantive messages were found, to advance the window.

### Step 7: Report

- How many messages reviewed
- How many captures created (with filenames)
- How many skipped (with brief reason)
- Key themes across the captures (if patterns emerged)

## Error Handling

| Situation | Behavior |
|---|---|
| WebFetch fails on a URL | Create capture anyway; note "Could not fetch article content"; record URL as source |
| Slack MCP unavailable | Show error; stop gracefully; do not create captures |
| `_strategy/` empty | Skip tagging; note "No strategic areas defined" |
| `_inbox/captures/` empty | No captures to find connections in; check people/projects only |
| Duplicate slug for same date | Append `-2`, `-3`, etc. |
| No argument provided | Ask the user what they want to capture |

## Design Principles

- **Raw thoughts are sacred.** Never edit, summarize, or paraphrase the user's own words in the raw thoughts section.
- **Tags must match filenames.** Strategic area tags come from `_strategy/` filenames. No freeform tags.
- **Connections should be genuine.** Zero connections is fine. Forced connections erode trust.
- **Slugs should be descriptive.** The filename should tell you what the capture is about.
- **Pull mode is batch manual mode.** Every triaged message goes through the same capture process as manual mode.
