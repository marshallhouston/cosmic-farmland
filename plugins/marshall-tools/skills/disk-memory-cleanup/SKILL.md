---
name: disk-memory-cleanup
description: Use when the user asks to clean up disk space, manage storage/memory, free up space, or says "/disk-memory-cleanup". Runs the automated cleanup script first, then investigates deeper for new space hogs.
version: 0.1.0
---

# Disk Cleanup

Two-phase disk space recovery: automated safe cleanup, then investigative audit.

## Phase 1: Automated cleanup

Run the cleanup script which handles safe, repeatable wins:

```bash
~/bin/disk-cleanup
```

This clears: Homebrew cache, Brave browser caches, Claude desktop updater cache, Spotify cache, and iMessage attachments older than 2 months.

## Phase 2: Investigative audit

After the script runs, dig deeper:

1. **APFS overview** — run `diskutil apfs list disk3` and report real used/free (not the misleading `df` numbers)
2. **Home directory scan** — `du -sh ~/*` sorted by size, top 15
3. **Library deep dive** — break down ~/Library by subfolder, flag anything over 500MB
4. **Application Support** — `du -sh "$HOME/Library/Application Support"/*` sorted, top 10
5. **Containers** — check for bloated app containers
6. **Caches regrowth** — compare current cache sizes to see what's grown back

## Phase 3: Recommendations

Present findings as a table with:
- Item, size, what it is, whether it's safe to delete, and expected impact

Only recommend deleting things that are clearly safe. For anything ambiguous, ask first.

## Important notes

- The Claude VM (~10 GB in Application Support/Claude) is needed for Cowork — don't recommend deleting it
- Photos library is intentional — don't recommend deleting it
- Playwright browsers may be needed for Stack System scraping — flag but don't auto-delete
- Apple Intelligence is disabled on this Mac — if related caches reappear, flag it
- Messages retention is set to 1 year — the script handles attachment pruning beyond 2 months
