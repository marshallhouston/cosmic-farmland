---
name: obsidian-setup
description: "One-time bootstrap for the obsidian-weaver plugin. Use when the user says '/obsidian-setup', 'set up obsidian', 'initialize vault', 'get started with obsidian-weaver', or when /today, /capture, or /connect-sync fails because OBSIDIAN_VAULT isn't set or the vault isn't seeded."
---

# /obsidian-setup — Bootstrap an Obsidian vault for this plugin

Walks the user through wiring their vault up to the `today`, `capture`, and `connect-sync` skills. Safe to run multiple times — each step is idempotent and will skip or prompt before overwriting.

## What this does

1. Confirms `OBSIDIAN_VAULT` is set and points at a real directory.
2. Copies `CLAUDE.md.template` into the vault as `CLAUDE.md` (if none exists).
3. Copies the `_connections-seed/` scaffolding into the vault as `_connections/`.
4. Checks for the optional `obsidian` CLI.
5. Prints next steps.

## Step 1: Check / set `OBSIDIAN_VAULT`

Run:

```bash
echo "${OBSIDIAN_VAULT:-UNSET}"
```

**If `UNSET` or empty:**

Ask the user for their vault's absolute path (e.g. `~/notes`, `~/Documents/MyVault`). Then:

- Offer to add `export OBSIDIAN_VAULT="<path>"` to their shell rc file (`~/.zshrc` for zsh, `~/.bashrc` for bash). Detect the shell via `echo $SHELL`. Only append if the line isn't already there — use `grep -q "OBSIDIAN_VAULT" ~/.zshrc || echo 'export OBSIDIAN_VAULT=...' >> ~/.zshrc`.
- For the current session, also run `export OBSIDIAN_VAULT="<path>"` so subsequent steps work without restarting the shell.
- Remind the user to `source ~/.zshrc` (or open a new terminal) before running `/today`, `/capture`, or `/connect-sync` in future sessions.

**If the path doesn't exist:** Ask whether to `mkdir -p` it (new vault) or correct the path (typo).

**If set and valid:** Continue.

## Step 2: Seed `CLAUDE.md`

Check if `$OBSIDIAN_VAULT/CLAUDE.md` already exists.

- **If it exists:** Ask whether to leave it alone, append the template as a new section, or overwrite (back up the old one to `CLAUDE.md.bak` first). Default: leave alone.
- **If not:** Copy `${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.md.template` to `$OBSIDIAN_VAULT/CLAUDE.md`:

```bash
cp "${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.md.template" "$OBSIDIAN_VAULT/CLAUDE.md"
```

Then open it for the user to fill in (or print the path and remind them it has `{{Your Name}}`, `{{ACRONYM}}`, etc. placeholders to replace).

## Step 3: Seed `_connections/`

Check if `$OBSIDIAN_VAULT/_connections` already exists.

- **If it exists:** Skip and tell the user. Don't overwrite — the registry may already have real data.
- **If not:** Copy the seed folder:

```bash
cp -r "${CLAUDE_PLUGIN_ROOT}/templates/_connections-seed" "$OBSIDIAN_VAULT/_connections"
```

Tell the user to open `$OBSIDIAN_VAULT/_connections/.registry.json` and replace the sample entries (Derrick Henry, Platform Migration, etc.) with their real people, themes, concerns, and decisions. Point them at `$OBSIDIAN_VAULT/_connections/README.md` for the schema.

## Step 4: Confirm the `Paths` table in `CLAUDE.md`

The template ships with default paths (`_weekly/_daily/` for daily notes, `_inbox/captures/` for captures, etc.). Skills read this table at runtime — they don't hardcode paths anymore.

- Open `$OBSIDIAN_VAULT/CLAUDE.md` and find the `## Paths` section.
- Ask the user whether the defaults match their vault. The most common override is the daily-notes path, since Obsidian's daily-note plugin lets users pick any folder.
- If the user wants a different daily-notes folder (e.g. `daily/`, `journal/`, `Daily Notes/`), edit the `daily_notes` row in the table in place.
- Same goes for `captures`, `templates`, `connections`, `people`, `projects`, `strategy` if the user has existing folders they want to map to.

If the user already had a `CLAUDE.md` (Step 2 left it alone) and it doesn't have a `Paths` section, offer to append the default `Paths` table from `${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.md.template` to the end of their file. Ask before appending.

**Special case — non-default `connections` path.** The `connect-sync.py` script reads an `OBSIDIAN_CONNECTIONS` env var to locate the connections folder (defaults to `$OBSIDIAN_VAULT/_connections`). The script doesn't parse `CLAUDE.md`, so if the user set `connections` to anything other than `_connections/` in the Paths table, the env var needs to mirror it — otherwise cron runs of `connect-sync.py` will write to the wrong place.

If the user's `connections` path is the default (`_connections/`), do nothing here — no env var needed.

If they changed it, offer to append to their shell rc:

```bash
export OBSIDIAN_CONNECTIONS="$OBSIDIAN_VAULT/<their connections value>"
```

Detect shell via `$SHELL` and append to `~/.zshrc` or `~/.bashrc`, gated on `grep -q OBSIDIAN_CONNECTIONS ~/.zshrc || ...` so re-runs don't duplicate. Also `export` it for the current session.

## Step 5: Offer to create missing folders

Skills write files to the folders listed in the `Paths` table. If a folder is missing, the underlying write will fail (the `obsidian` CLI usually creates parents, but direct file writes don't). Rather than letting the user hit a failure on first `/capture`, offer to create them now.

**Check each path in the `Paths` table:**

```bash
for p in daily_notes captures templates strategy people projects; do
  # resolve <p> to its path value from CLAUDE.md, then:
  test -d "$OBSIDIAN_VAULT/<value>" && echo "✓ <value>" || echo "✗ <value>"
done
```

`_connections/` was already seeded in Step 3 — don't re-check it here.

**Print a status block**, e.g.:

```
Your Paths table points at these folders. Current state:

  ✓ _connections/         (seeded by this script)
  ✗ _weekly/_daily/       (missing — /today and /connect-sync need this)
  ✗ _inbox/captures/      (missing — /capture needs this)
  ✗ _templates/           (missing — /today and /capture need this)
  ✗ _strategy/            (missing — /capture tags against this)
  ✓ _people/
  ✗ _projects/            (missing — /capture writes project pages here)
```

**If nothing is missing:** skip this step.

**If anything is missing:** use `AskUserQuestion` (Claude Code's multi-select tool) to ask which to create. One option per missing folder, all default-checked, plus a "create nothing" option. Prompt text: *"Create missing folders in your vault? Uncheck any you want to handle yourself."*

Then:

```bash
mkdir -p "$OBSIDIAN_VAULT/<selected path>"
```

for each selected path. Report what was made.

**If the user declines all:** warn them — `/capture` will fail on first run until `_inbox/captures/` exists, `/today` will fail until `<daily_notes>/` exists. They know; move on.

## Step 6: Check for the `obsidian` CLI (optional)

Run:

```bash
command -v obsidian || echo "not installed"
```

The skills degrade gracefully without it (fall back to direct file reads/writes), but it makes `today` and `capture` smoother. If not installed, tell the user it's optional and point them to whichever `obsidian` CLI they want (there are several — this plugin assumes one that exposes `daily:read`, `daily:append`, `create`, `tasks`, `search:context`, `read`, `links`, `backlinks`, `rename`, `tags`). Don't pick one for them.

## Step 7: Print next steps

Summarize what's ready and what's left:

```
Setup complete.

✓ OBSIDIAN_VAULT = <path>
✓ CLAUDE.md seeded        (edit placeholders: role, people, projects, terms)
✓ Paths table reviewed    (daily_notes, captures, etc. match your vault)
✓ Folders created         (or skipped per your choice)
✓ _connections/ seeded    (edit .registry.json with your real entities)
? obsidian CLI            (optional — skills degrade without it)

Try:
  /today              — create or open today's daily note
  /capture <thought>  — dump an idea into _inbox/captures/
  /connect-sync today — scan today's notes and link them into the graph
```

## Step 8: Offer automation (optional)

These skills are manually triggered by default. Ask the user whether they want anything running on a schedule. If yes, offer three options — pick based on their answer, don't install anything without confirmation:

**A. OS cron / launchd for `connect-sync.py`.** Best for passive graph maintenance. The script has zero deps and doesn't need the LLM for pattern-matching mode. Offer to draft a crontab line like:

```cron
0 */2 * * *  OBSIDIAN_VAULT=/path/to/vault python3 "${CLAUDE_PLUGIN_ROOT}/scripts/connect-sync.py"
```

Resolve `CLAUDE_PLUGIN_ROOT` to the actual path when drafting (the user's cron doesn't inherit that env var). Show the line and tell them to run `crontab -e` themselves — don't install it.

**B. `/schedule` (Claude Code scheduled remote agents).** Best for runs that need the LLM — e.g. `/connect-sync deep` nightly for entity discovery, or `/today` at 6am to pre-build the daily note. Point the user at the `schedule` skill; don't invoke it yourself unless they explicitly ask.

**C. `/loop` (in-session interval).** Best for "keep syncing while I work today." Runs inside an open session only.

**If they're not sure:** recommend (A) with a 2-hour interval — it's the lowest-risk, doesn't require Claude Code open, and covers the 90% use case.

## Edge cases

- **Vault is not a git repo:** That's fine. Mention that you'd recommend `git init` inside the vault so changes are recoverable, but don't require it.
- **`CLAUDE_PLUGIN_ROOT` unset:** This means the plugin isn't installed as a Claude Code plugin (maybe being run by reading files directly). Fall back to walking up from the skill file's own path, or ask the user to point at the plugin directory.
- **User runs `/obsidian-setup` again later:** Each step detects prior state and skips or prompts. Never silently overwrite existing files.
