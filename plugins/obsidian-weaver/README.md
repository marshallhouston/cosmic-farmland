# obsidian-weaver

Claude Code as the interface to your Obsidian vault — and a background process that weaves connections between your notes as you write them. Daily planning, quick captures, and an auto-maintained knowledge graph in one plugin. Install once, point it at any vault via `$OBSIDIAN_VAULT`, and `/today`, `/capture`, and `/connect-sync` work from anywhere.

## Install

In Claude Code:

```
/plugin marketplace add marshallhouston/tools
/plugin install obsidian-weaver@cosmic-farmland
```

Then run `/obsidian-setup` (see [Quick start](#quick-start)).

## The pattern

```
Claude Code  ──(reads/writes markdown)──▶  Obsidian vault
     │                                           │
     │                                           ▼
     └──(invokes)──▶ skills & scripts    Obsidian renders graph,
                                         tags, backlinks, daily notes
```

- **Claude Code** is the interface. You talk to it; it runs skills.
- **Obsidian** is the filesystem and visualizer. Plain markdown with `[[wikilinks]]` and `#tags`.
- **Skills** are the verbs (`/today`, `/capture`, `/connect-sync`).
- **The optional `obsidian` CLI** is the bridge — skills use it when present, fall back to direct file I/O when not.

## Skills

| Skill | What it does |
|-------|--------------|
| `/obsidian-setup` | One-time bootstrap: checks `OBSIDIAN_VAULT`, seeds `CLAUDE.md` and `_connections/` in your vault |
| `/today` | Opens or creates today's daily note (calendar sync + carryover from previous days + meeting note files) |
| `/capture` | Turns a brain dump or article URL into a structured note in `_inbox/captures/` with auto-tagging and connection finding |
| `/connect-sync` | Scans recently modified notes, finds mentions of known themes/people/concerns/decisions, maintains a `_connections/` knowledge graph automatically |

## A day in the loop — what using this actually feels like

To show how the three skills string together, here's a realistic slice of a day. The project is **Platform Migration** (moving services from EC2 to Kubernetes, Q3 deadline). The philosophy running through it is something I've been developing in a strategy doc called **"Boosting Builders, Not Nagging Naysayers"** (BBNNN) — the idea that I invest my 1:1 energy in the people generating momentum rather than trying to convert the skeptics. Both of these are registered as entities in `_connections/.registry.json`, which is how the graph finds them.

> **Day one looks quiet — that's normal.** On your first run you'll have an empty vault (or an existing vault with nothing registered yet), a registry with two or three sample entities you haven't replaced, and a `/connect-sync` that reports "no changes" because there's nothing to weave together yet. That's fine. The system compounds — the first week is seeding, the payoff arrives after you've written across enough surfaces that patterns emerge. If day one feels underwhelming, you've set it up correctly.

**8:43am — `/today`.** Opens my daily note. It pulls three unchecked items from the last few days: *"follow up with King on the rollback assumption" (2 days old), "draft BBNNN section on feedback loops" (4 days old — probably drop), "review Julio's migration timeline"*. Asks my focus — I say "finish the BBNNN strategy doc, prep for 1:1 with King." It lists today's calendar events as meeting note stubs: `2026-04-17-1on1-king-henry.md`, `2026-04-17-platform-migration-weekly.md`.

**9:30am — 1:1 with King Henry.** I take notes directly in `2026-04-17-1on1-king-henry.md`. King is the person I keep describing internally as the archetypal "builder" — he's the one actually shipping on the Platform Migration work. I write things like *"king unblocked the service mesh config — this is exactly the boosting-builders pattern, I should put cycles here, not on defending the migration to the skeptics"* and *"open question on rollback assumption from last week still unresolved — he's going to pair with julio today."*

**11:15am — `/capture` while walking back from coffee.** `/capture realized the BBNNN framing explains why I keep bouncing off 1:1s with the platform critics — trying to convert them drains energy that compounds better on builders like king and julio. worth a section in the strategy doc about investment allocation.` A file lands at `_inbox/captures/2026-04-17-bbnnn-investment-allocation.md`, auto-linked to `[[Boosting Builders Not Nagging Naysayers]]`, `[[king-henry]]`, `[[julio-jones]]`, and `[[Platform Migration]]` — all entities the script recognized from the registry.

**2:00pm — strategy doc work.** I open `_strategy/boosting-builders-not-nagging-naysayers.md` and write a new section on investment allocation, pulling quotes from the 1:1 note and the capture. I don't manually add any links — just reference concepts and people by name.

**4:53pm — `/connect-sync today`.** Scans the 7 notes I touched. Reports:

```
Synced 7 notes → 18 new links added
- 2026-04-17-1on1-king-henry → [[Platform Migration]], [[Boosting Builders Not Nagging Naysayers]]
- 2026-04-17-bbnnn-investment-allocation → [[Boosting Builders Not Nagging Naysayers]], [[king-henry]], [[julio-jones]], [[Platform Migration]]
- _strategy/boosting-builders-not-nagging-naysayers → [[king-henry]], [[julio-jones]]
- 2026-04-17-platform-migration-weekly → [[Platform Migration]], [[king-henry]]
- ...
```

Each of those source notes now has a `## Connections` section pointing back to the theme/person pages. The BBNNN strategy page now lists every 1:1 and capture where I've applied the frame. The Platform Migration page now lists every meeting, 1:1, and decision that's touched it.

**One week later — the shape starts to emerge.** I open `_connections/themes/Boosting Builders Not Nagging Naysayers.md` and already see 8 linked source notes: 3 one-on-ones (all with King and Julio, interestingly), 2 captures, the strategy doc, 2 weekly meeting notes. What's satisfying isn't the count — it's that I never thought about linking any of it. I just wrote. The Platform Migration page has 14 linked notes and the first clusters are visible in Obsidian's graph: King sits at a dense hub, the strategy doc bridges people and project, a concern I'd forgotten about from Monday (*"release cadence friction"*) is already wired in.

**One month later — the graph is beautiful.** The BBNNN page has 31 linked sources. The Platform Migration page has 47. But the real payoff is the second-order stuff — things the script surfaced that I wouldn't have noticed manually. BBNNN and Platform Migration share 12 overlapping source notes, which means the philosophy is actually showing up in the project work (not just in strategy-doc abstractions). A concern called *"morale on platform team"* emerged in deep mode — it started as scattered mentions across three 1:1s and now has its own page linking back to all of them. (Deep mode is how the system catches things you haven't registered yet: `/connect-sync deep` asks Claude to review notes the pattern-matcher flagged as unclassified, proposes new themes or concerns with evidence, and only creates pages after you confirm — nothing is auto-invented behind your back.) Opening Obsidian's graph view, the whole thing looks like an organism: clusters of thought around projects, spokes radiating out to people, and bridges between themes that reveal where my thinking is actually consistent versus where I'm drifting. I didn't design this shape. It emerged because the sync script kept weaving while I kept writing.

That's the loop. Morning `/today` to frame the day. `/capture` throughout. `/connect-sync` at the end (or on cron in the background). The compound is that your philosophical threads (*"boosting builders, not nagging naysayers"*) and your concrete projects (*"Platform Migration"*) get cross-indexed automatically — so you can see the relationship between what you say matters and where your time actually goes.

## Requirements

- **Python 3.6+** — needed for `/connect-sync`'s pattern-matching script. Zero third-party deps; pure stdlib. macOS 11+ and any Homebrew Python satisfy this by default.
- **An Obsidian vault** (a directory of markdown files). Doesn't have to be a git repo, but recommended.
- **Optional: an `obsidian` CLI** — see below.

## Quick start

1. **Install the plugin** (see [Install](#install) above).

2. **Set `OBSIDIAN_VAULT`** to your vault's absolute path. Either in your shell rc:

   ```bash
   export OBSIDIAN_VAULT="$HOME/my-vault"
   ```

   Or let `/obsidian-setup` do it for you.

3. **Run `/obsidian-setup`** in any Claude Code session. It will:
   - Confirm the env var is set
   - Copy `CLAUDE.md.template` into your vault as `CLAUDE.md` (with placeholders to fill)
   - Copy `_connections-seed/` into your vault as `_connections/` (sample registry you replace with your real entities)
   - Check for the optional `obsidian` CLI
   - Tell you what's next

4. **Fill in `$OBSIDIAN_VAULT/CLAUDE.md`** — your role, key people, active projects, preferences. This is loaded every time Claude Code runs from inside the vault and is what makes skills feel personalized.

5. **Edit `$OBSIDIAN_VAULT/_connections/.registry.json`** with your real themes, people, concerns, decisions. See `_connections/README.md` in your vault for the schema.

6. **Try it out:**

   ```
   /today
   /capture just had an idea about the migration rollback plan
   /connect-sync today
   ```

## Vault layout the skills assume

```
$OBSIDIAN_VAULT/
├── CLAUDE.md           # Context loaded by Claude Code (seeded by /obsidian-setup)
├── _templates/         # Your note templates (you define; not shipped by plugin)
├── _weekly/_daily/     # Daily notes — matches Obsidian's daily-note plugin
├── _inbox/captures/    # Output of /capture
├── _strategy/          # Strategic area pages (used as tags by /capture)
├── _people/            # One file per person
├── _projects/          # One file per project
└── _connections/       # Auto-maintained knowledge graph (seeded by /obsidian-setup)
    ├── .registry.json
    ├── themes/
    ├── people/
    ├── concerns/
    └── decisions/
```

The paths aren't hardcoded — skills reference them as conventions. If your vault is laid out differently, edit the paths in `CLAUDE.md` and the individual SKILL.md files. The connect-sync script defaults to `$OBSIDIAN_VAULT/_connections`; to relocate it, export `OBSIDIAN_CONNECTIONS` (see the note in the Automation section below).

## The `obsidian` CLI (optional)

The `today` and `capture` skills prefer a CLI named `obsidian` for:

- `obsidian daily:read` / `daily:append` / `daily:path`
- `obsidian create name="..." template="..."`
- `obsidian tasks todo file="..." verbose`
- `obsidian task file="..." line=N done`
- `obsidian read file="..."` / `search:context query="..."`
- `obsidian links file="..."` / `backlinks file="..."`
- `obsidian tags file="..."`

There are several community CLIs with this shape — pick one, or write thin wrappers. Skills fall back to direct file reads/writes if the CLI isn't on `$PATH`.

## How `/connect-sync` works

You mention "k8s migration" across five meeting notes over two weeks. The sync script:

1. Watches for modified `.md` files since the last run.
2. Pattern-matches your notes against `_connections/.registry.json`.
3. Updates `_connections/themes/k8s-migration.md` with new source-note links.
4. Injects a `## Connections` section into each source note pointing back to the theme page.
5. In deep mode (LLM-powered), detects NEW themes/people/concerns you haven't registered yet.

Obsidian's graph view then shows your thinking as it evolves.

## Automation — making this recurring

The skills are manually triggered by default. Three ways to make them run on a schedule, ordered from lowest to highest ceremony:

**1. OS cron / launchd — recommended for passive graph maintenance.** The `connect-sync.py` script has zero dependencies and runs without Claude Code being open. Point macOS `launchd` or a standard crontab at it:

```cron
# Every 2 hours, pattern-sync any modified notes
0 */2 * * *  OBSIDIAN_VAULT=/path/to/your/vault python3 /path/to/plugins/obsidian-weaver/scripts/connect-sync.py
```

Deep mode (LLM entity detection) isn't covered by this — it needs Claude Code. But pattern-sync against your registered entities is the 90% use case.

> **Note:** `connect-sync.py` ships with a `#!/usr/bin/env python3` shebang but isn't marked executable by default. If you want shorter cron/launchd lines, run `chmod +x /path/to/plugins/obsidian-weaver/scripts/connect-sync.py` once and you can drop the `python3` prefix. Not required.
>
> **If you moved `_connections/`** somewhere other than `$OBSIDIAN_VAULT/_connections` (e.g. you edited the `connections` row in your `Paths` table), also export `OBSIDIAN_CONNECTIONS="$OBSIDIAN_VAULT/your-path"` in the cron env. Otherwise the script writes to the default location. `/obsidian-setup` offers to do this for you.

**2. `/schedule` — Claude Code scheduled remote agents.** Useful when you want a skill that needs the LLM to fire on a schedule. Examples:

- `/schedule '/connect-sync deep'` to run nightly and discover new entities you haven't registered yet.
- `/schedule '/today'` to have the daily note pre-built at 6am.

Output lands wherever you've configured delivery for remote agents.

**3. `/loop` — in-session interval.** Runs a prompt every N minutes inside an open Claude Code session. Fine for "keep syncing while I work today," not for unattended scheduling.

The `/obsidian-setup` skill offers to help you pick one at the end of setup. Automation is always opt-in — this plugin installs nothing on your system without asking.

## Using outside Claude Code

The SKILL.md workflows are agent-agnostic — only the wiring is Claude Code-specific. To port to Cursor or another agent:

- `AskUserQuestion` (used by `today` and `capture` for multi-select) → replace with plain-text prompting ("Reply with the numbers you want to carry forward").
- Skill frontmatter + the `Skill` tool → Cursor Rules or custom commands, equivalent in other agents.
- `${CLAUDE_PLUGIN_ROOT}` in `connect-sync` skill → hardcode the plugin path or set an env var your agent exposes.

## Make it yours

This plugin is a starting point, not a finished product. The three skills I ship are the ones I hit friction with first — yours will be different. Rename things, delete what you don't use, add what you miss. The whole value of a personal knowledge system is that it's *personal*; don't let someone else's idea of "the daily loop" override your own.

I built this by **Build → Friction → Fix (BFF)**:

1. **Build** — start with the smallest thing that could work (a single `/today` skill, hardcoded paths, no automation).
2. **Friction** — use it. Notice what annoys you. Note it. *Don't* stop to fix it.
3. **Fix** — when the friction is clear and the pattern is real, improve the system.

I BFF'd this plugin into existence over months and watched what actually emerged. The knowledge graph wasn't part of the original plan — it showed up because I kept typing the same person's name across different notes and wanting them linked. `/connect-sync` is the *fix* for that friction.

Your friction will be different. Let it drive what you build next. Some examples of skills worth building when you hit the relevant friction — but don't build these pre-emptively:

- `/status` — project status pulled from issue tracker + chat + vault (build when you keep re-assembling the same summary)
- `/draft` — write messages in your voice (build when you notice Claude's defaults don't sound like you)
- `/strategy` — structured framework for working through a strategy doc (build when you've written the same kind of doc three times)
- `/time-audit` — map calendar to stated priorities (build when you suspect your calendar doesn't match what you say matters)

More on the method: [marshallhouston.wtf/build-friction-fix](https://marshallhouston.wtf/build-friction-fix/). It applies to anything you build for yourself, not just this plugin.

## Credit

Originated by [Marshall Houston](https://marshallhouston.wtf) — BFF'd into existence over months of daily use. Shared in the spirit of hyper-personalized software: take what helps, discard what doesn't, rebuild for yourself.
