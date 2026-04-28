# CC Friction Systematizer — Usage Guide

**Status:** Living doc. Companion to the forthcoming blog post; also useful standalone if you cloned the repo.

Audience: someone who read the blog post, cloned `cosmic-farmland`, and wants to run the friction loop on their own Claude Code sessions.

## What you get

A local-only pipeline over your own `~/.claude/projects/*.jsonl` transcripts:

1. **Export** — flatten JSONL into CSVs you can query.
2. **Scan** — heuristic regexes flag friction moments (copy clarity, re-asking, interrupts, stalls, rule drift, status begging).
3. **Mine** — surface recurring workflow patterns worth turning into commands.
4. **Peek** — drill into a single session's friction in detail.
5. **Systematize** — promote findings up the enforcement stack (hook > CI > script > doc) via `/systematize`.

Nothing leaves your laptop. No telemetry server, no API keys.

## Prereqs

- macOS or Linux. Apple Silicon tested.
- Python 3.11+ (stdlib only — no pip installs).
- [Claude Code](https://claude.com/claude-code) installed and used enough to have transcripts at `~/.claude/projects/`.
- Optional: `duckdb` for ad-hoc SQL over the CSVs.
  ```
  brew install duckdb
  ```
  Skip if you only want the canned scans.

## Install

```
git clone https://github.com/marshallhouston/cosmic-farmland ~/code/cosmic-farmland
export PATH="$HOME/code/cosmic-farmland/bin:$PATH"
```

Add the `PATH` line to `~/.zshrc` or `~/.bashrc` to keep it.

To get the `/systematize`, `/wrap`, `/ship-all` commands and the no-reasking hook inside Claude Code:

```
/plugin install cosmic-farmland@cosmic-farmland
/reload-plugins
```

## Bump retention first

Default `cleanupPeriodDays` is ~30. Bump it before mining so you have history. Edit `~/.claude/settings.json`:

```json
{ "cleanupPeriodDays": 365 }
```

Or `0` for never. Do this on day one — past sessions you've already lost are gone.

## Workflow

### 1. Export sessions to CSV

```
cc-session-export
```

Walks `~/.claude/projects/*/*.jsonl`, writes:

- `~/cc-telemetry/messages.csv` — one row per message, with token usage.
- `~/cc-telemetry/sessions.csv` — one row per session, aggregated.

Idempotent. Re-run any time. Prints top-line totals when done.

For ad-hoc SQL:

```
cc-session-export --duckdb
```

Opens a DuckDB shell with `messages` and `sessions` views pre-loaded. Requires `duckdb` on PATH.

### 2. Scan for friction across recent sessions

```
cc-friction-scan
```

Walks the last 7 days of sessions, applies the regex taxonomy from `docs/cc-friction-systematizer.md`, prints top-N candidates ranked by recurrence × severity. Heuristic-only. No LLM call.

Read the output. The high-frequency rows are the ones worth fixing.

### 2b. Classify candidates with an LLM (optional)

```
cc-friction-classify --from-doc --per-session 20
```

Heuristic regex over-fires (~40% false-positive rate in our calibration). The classifier sends each candidate's transcript slice to Claude and returns a JSON verdict per row: real friction y/n, taxonomy bucket, recommended fix tier, confidence, one-sentence rationale.

Auth: reads your Claude Max OAuth token from the macOS keychain (`security find-generic-password -s "Claude Code-credentials"`). No `ANTHROPIC_API_KEY` required.

Defaults to Haiku 4.5 for cost. `--model claude-opus-4-7` for max accuracy if Max plan permits (Opus on personal Max plans tends to 429 immediately — fall back to Haiku).

Output lands at `~/cc-telemetry/friction-classified.jsonl`, resume-safe across runs.

Skip this step if heuristic-only signal is already actionable.

### 3. Mine recurring workflow patterns

```
cc-pattern-mine
```

Looks for command sequences you keep running (e.g. `/ship` → `/ship` → `/ship`, or `/ship` → `/handoff`). Output ranks candidates worth collapsing into a single command. This is how `/ship-all` and `/wrap` were derived.

### 4. Drill into a single session

```
cc-friction-peek <session_id>
```

For one session UUID (the part of the JSONL filename before `.jsonl`):

- Lists all user messages.
- Shows tool-call sequences.
- Top 5 highest-output assistant messages (verbosity / big-diff candidates).

Use this when a scan flags a session and you want context before deciding what to fix.

### 5. Systematize a finding

In Claude Code:

```
/systematize
```

Describe the recurring friction. The skill picks the highest viable enforcement tier (hook > CI > script > doc > memory) and ships the artifact. Memory is last resort — see `~/.claude/CLAUDE.md` memory-discipline section.

## Where things live

| Thing | Path |
|---|---|
| Source transcripts | `~/.claude/projects/<encoded-cwd>/*.jsonl` |
| Flattened CSVs | `~/cc-telemetry/messages.csv`, `~/cc-telemetry/sessions.csv` |
| Hook log | `~/.claude/cc-friction-log.jsonl` |
| Plugin source | `~/code/cosmic-farmland/plugins/cosmic-farmland/` |
| Scripts | `~/code/cosmic-farmland/bin/` |
| Design notes | `~/code/cosmic-farmland/docs/cc-friction-systematizer.md` |

Nothing in this loop writes into the cloned repo. Outputs go to `~/cc-telemetry/` and `~/.claude/`.

## Privacy

Your transcripts contain everything you've typed and everything Claude has output across every project. Treat `~/cc-telemetry/` and `~/.claude/projects/` as sensitive. Don't paste raw scan output anywhere public without redacting.

The repo's `.gitignore` excludes `out/` and `graphify-out/`, but you should never run these scripts with the repo as the output target anyway — the defaults write to your home dir.

## When to skip this

- Fewer than ~10 sessions of CC history. Heuristics need volume.
- You don't already have recurring frictions you can name. Building this before you have the itch is premature — re-read the BFF section in the design doc.

## Pointers

- Design rationale and open questions: `docs/cc-friction-systematizer.md`
- Issues: https://github.com/marshallhouston/cosmic-farmland/issues

## Known rough edges

- `cc-friction-peek` is hardcoded to the preach-hub project dir (calibration leftover). Edit the path before using on your own sessions, or follow up via PR.
- `cc-session-export --duckdb` will fail with a raw `execvp` error if `duckdb` isn't on PATH. Install it (`brew install duckdb`) or skip the flag.
- No screenshots yet; output is plain text designed to skim in a terminal.
