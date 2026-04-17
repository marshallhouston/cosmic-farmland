---
description: Sync recent Granola meeting notes into ~/marshall.notes/meetings/ as markdown
---

Pull Granola meetings and write them as markdown files into `~/marshall.notes/meetings/`.

Steps:
1. If `$ARGUMENTS` is empty, use `time_range: last_week`. If `$ARGUMENTS` is "month", use `last_30_days`. If it's "week", use `this_week`. Otherwise pass it through.
2. Call `mcp__granola__list_meetings` with that range.
3. For each meeting, check if `~/marshall.notes/meetings/YYYY-MM-DD-<slug>.md` already exists (slug = title lowercased, spaces→dashes, dashes-only per feedback_vault_dashes). Skip existing files.
4. For new meetings, call `mcp__granola__get_meetings` in batches of up to 10 to fetch full content.
5. Write each one as markdown with frontmatter:
   ```
   ---
   title: <meeting title>
   date: <ISO date>
   attendees: [<list>]
   granola_id: <uuid>
   ---

   # <title>

   ## Summary
   <AI summary>

   ## Notes
   <private notes>

   ## Action Items
   <if any>
   ```
6. Create the `meetings/` directory if it doesn't exist.
7. Report what was written and what was skipped. Keep it terse.
