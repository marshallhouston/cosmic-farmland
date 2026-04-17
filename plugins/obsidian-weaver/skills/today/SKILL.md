---
name: today
description: "Daily note creator — calendar sync, carryover items from previous days, and meeting file setup. Use when the user says 'today', '/today', 'daily note', 'start my day', 'morning planning', or any variation of wanting to set up their day."
args: "[quick]"
---

# /today — Daily Note Creator

Create or open today's daily planning note. Handles calendar sync, carryover from the past 7 days, and meeting note file creation.

## Modes

- **Normal mode** (`/today`): Full interactive flow — prompts for focus area, lets you choose which carryovers to keep
- **Quick mode** (`/today quick`): Skips the focus area question and auto-selects recent carryovers (0-2 days old)

## Obsidian CLI Usage

This skill uses the `obsidian` CLI to interact with the vault. Key commands:

- `obsidian daily:read` — returns content of today's daily note (empty if none exists)
- `obsidian daily:path` — returns the expected path for today's daily note
- `obsidian tasks todo file="YYYY-MM-DD" verbose` — incomplete tasks with line numbers
- `obsidian task file="YYYY-MM-DD" line=N done` — toggle a task complete
- `obsidian create name="..." template="..."` — create a meeting note from a template

If the `obsidian` CLI isn't installed, fall back to direct file reads/writes via the standard tools.

## Step 1: Check for Existing Note

```bash
obsidian daily:read
```

**If output contains content:** Display it. Stop. Do not modify.

**If empty:** Proceed to create a new daily note.

## Step 2: Sync Calendar (Optional)

If you have a calendar sync script (e.g., one that pulls from Google Calendar via `.ics` URL or API), run it:

```bash
python sync_calendar.py --date YYYY-MM-DD
```

The script should write events to a known location (e.g., `_calendar/YYYY-MM-DD-agenda.md`) that this skill can read.

**If you don't have calendar sync:** skip this step. The user can paste meetings manually or fill them in later.

**If sync fails:** ask the user whether to retry, continue with empty Meetings section, or abort.

## Step 3: Ask for Focus Area (Normal mode only)

> What are your main focus areas or theme for today? (type your response, or say "skip")

Focus areas are general themes ("clarity of thought", "deep work", "ship the migration"). They are NOT action items — they go at the top of the file as plain text, before any section.

Quick mode skips this.

## Step 4: Scan for Carryover Items

Look at the last 7 calendar days of daily notes (yesterday going back 6 more days) in the daily-notes folder. Read the path from the `Paths` table in the vault's `CLAUDE.md` (key `daily_notes`).

**If `$OBSIDIAN_VAULT/CLAUDE.md` is missing or has no `Paths` table**, stop and tell the user to run `/obsidian-setup` first. Do not guess a path.

**Algorithm:**

1. For offsets `d = 1..7`, compute the date and look for the file `YYYY-MM-DD.md`. Process in order (most recent first).
2. If a file is missing for a date, skip it — do NOT extend the window to find more.
3. Build a "completed carryover" set from `- [x]` items that include `(carryover)` or `(carried forward X days)` markers (this prevents re-suggesting items that have already been carried forward and completed).
4. Scan `- [ ]` items in older notes; present only those whose normalized text isn't in the completed set.
5. Track each item's carryover age — items annotated `(carried forward X days)` have age X.

**Filter out:**
- Empty checkboxes (`- [ ]` with no text)
- Items in the Meetings section (date-specific, never carry over)
- Date-bound or event-specific items: anything mentioning a specific date, "today", "this week", "tomorrow", or one-time events
- Duplicates

**What should carry over:**
- Ongoing work tasks
- Strategic or planning items
- Reading/research
- Administrative items without specific dates

## Step 5: Present Carryover Candidates

Use the AskUserQuestion tool with `multiSelect` to let the user choose which items to carry forward.

**Smart defaults:**

| Carryover Age | Default | Why |
|---|---|---|
| New (from yesterday) | Selected | Fresh tasks |
| 1-2 days | Selected | Likely still relevant |
| 3-6 days | Unselected | Force re-commit |
| 7+ days (stale) | Unselected, marked `[STALE - X days]` | User must opt in |

**Quick mode:** show all items in one list per section; defaults applied as above.

**Normal mode:** present stale items (7+ days) in a separate prompt FIRST so the user explicitly decides whether to keep them.

If there are more than 10 carryover candidates, split into multiple prompts by section (Actions, Other, Longer term).

## Step 6: Update Source Files (Audit Trail)

For every carryover candidate, update the source file where it came from. Every candidate gets an explicit annotation — carried, dropped, or declined.

**Carried forward** (user selected it):
```markdown
# Before
- [ ] review document

# After
- [x] carried over to YYYY-MM-DD - review document
```

**Dropped** (user explicitly dropped a stale item):
```markdown
- [x] dropped on YYYY-MM-DD - some stale task
```

**Declined** (user didn't select it):
```markdown
- [x] declined to carry over on YYYY-MM-DD - some task
```

**Nested tasks:** mark the parent and all incomplete children together.

This audit trail means you can always trace what happened to a task.

## Step 7: Create Today's Note

Target path: `<daily_notes>/YYYY-MM-DD.md`, where `<daily_notes>` is the value from the `Paths` table in the vault's `CLAUDE.md`. If the table is missing, stop and direct the user to `/obsidian-setup`.

**Before writing:** if `$OBSIDIAN_VAULT/<daily_notes>/` doesn't exist, ask the user: *"The folder `<daily_notes>/` doesn't exist in your vault. Create it? [y/n]"*. On `y`, run `mkdir -p "$OBSIDIAN_VAULT/<daily_notes>"` and continue. On `n`, stop and tell them to either create the folder manually or update the `daily_notes` path in `CLAUDE.md` to one that exists.

Write the file with this structure:

```markdown
[focus area as plain text, NOT a checkbox, before all sections]

## Actions
[carried-over Actions items, with `(carried forward X days)` annotation]

## Meetings
[transformed calendar events — see below]

## Other
[carried-over Other items]

## Longer term things
[carried-over Longer term items]
```

**Carryover count logic:**
- First time being carried: append `(carried forward 1 day)`
- Item already had `(carried forward N days)`: increment to `N+1`
- Nested children inherit their parent's annotation; don't annotate them individually

**Empty sections:** leave the heading but no placeholder checkboxes.

## Step 8: Calendar Event Transformation

For each calendar event, transform it into a checkbox with a wikilink to a meeting note file. **Create the meeting note file** so the wikilink isn't broken.

**Skip these events:** Out of office, OOO, Focus time, Lunch, Break, Commute, generic busy blocks.

**Common patterns** (adapt to your team's naming):

- 1:1s: `1:1 [[Person Name]]` → `[[YYYY-MM-DD-1on1-firstname-lastname]]`
- Team standups: `Team Standup` → `[[YYYY-MM-DD-team-standup]]`
- Other meetings: use the event name kebab-cased

Use `obsidian create name="..." template="..."` to create the meeting file from a template (e.g., a `1on1-template.md` in your `_templates/` folder).

**Meeting entry format:**
```
- [ ] [[YYYY-MM-DD-meeting-name]] - brief note from calendar description
```

Meeting checkboxes get checked when the meeting is attended.

## Step 9: Output

Confirm the file path so the user can open it in Obsidian.

If the user's focus area thematically connects to any carried-forward items, briefly mention the connection in your output. Keep it lightweight — one line, not a restructure.

## Filename Convention

All filenames use kebab-case: lowercase, hyphens for spaces, no special characters. `&` becomes `-and-`. Colons, parens, brackets are stripped.

Examples:
- `2026-04-15.md` (daily note)
- `2026-04-15-1on1-derrick-henry.md` (1:1)
- `2026-04-15-team-standup.md` (standup)
- `2026-04-15-quarterly-planning.md` (other meeting)
