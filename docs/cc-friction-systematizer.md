# CC Friction Systematizer

**Status:** prototype-pending. Idea captured 2026-04-26.

## Vision

Ask: *"top 3 frictions in last day. systematize them."*

Boom: analysis runs on real Claude Code session data → identifies recurring corrections, token waste, tool flailing, hook collisions → routes each to highest-tier fix (hook > CI > script > doc) via existing `/systematize`.

This is **BFF (Build Friction Fix) closed-loop** — the Friction step stops being manual journaling, becomes derived from observed sessions.

## Pieces (existing)

| Piece | Status | Where |
|---|---|---|
| Session JSONL transcripts | live, free | `~/.claude/projects/<encoded-cwd>/*.jsonl` (CC built-in, ~28d retention default) |
| Flat extract (CSV) | shipped | `cc-session-export` → `~/cc-telemetry/{messages,sessions}.csv` |
| OTel → Honeycomb | shipped | `claude-code` dataset, preach-hub-only |
| `/systematize` | shipped | cosmic-farmland plugin, promotes lesson up enforcement tier |
| DuckDB | shipped | `brew install duckdb`, queries CSV |

## Pieces (to build)

### 1. Friction signal extractor

**Heuristic pass first** (cheap, deterministic, legible). Flag candidates:

- High output tokens single msg (>5k) → big diff or rambling explanation
- User msg containing `no`, `stop`, `don't`, `wrong`, `not that` → correction
- Same tool name retried 3+ times w/ different args within N msgs → flailing
- Long tool output (>10k tokens) consumed context → waste
- Hook blocked tool call (PreToolUse exit ≠ 0) → known friction
- Sessions w/ avg_in_per_msg > Nx baseline → context bloat
- Long gaps between user msgs in same session → marshall walked away frustrated?

**LLM pass second** on top-N heuristic candidates only. Prompt the model: "given this transcript slice, what was the underlying friction? what could have prevented it?" Don't blanket-LLM the whole corpus.

### 2. Friction → systematize glue

For each surfaced friction:
- Classify: prompt issue / tool config / missing hook / missing skill / doc gap
- Hand to `/systematize` w/ the classification
- Skill picks highest viable enforcement tier

### 3. Skill `cf:cc-friction`

Wraps the above. **Build only after prompt + heuristics produce real signal across 5-10 hand-validated sessions.** Premature skill = slow iteration loop.

## Open questions to iterate

- **Definition of friction.** Token waste is one axis. User correction is another. Tool retry is third. Some overlap, some don't. Pick a primary axis or treat them as parallel detectors?
- **Sample size.** 1 day too noisy? 7d the right window? Per-session vs aggregate?
- **Prompt design.** Single mega-prompt vs chain (extract → classify → recommend)?
- **False-positive rate.** A correction isn't always friction — sometimes marshall just changed his mind. How to filter without losing real signal?
- **What gets surfaced vs auto-fixed?** Auto-systematize the obvious (e.g. repeated `bun test` → `bun run test` correction → enforce w/ hook). Surface only the ambiguous.

## Storage / future

Currently local: JSONL → CSV → DuckDB on disk. JSONL is source of truth; everything else derivable, regenerate any time.

Move remote when:
- Want cross-device analysis
- Want scheduled jobs running while laptop asleep
- Want to share friction patterns across users (team mode)

Options when it's time:
- **Railway Postgres** (already paying) — push CSVs nightly, query via `postgres_scanner` DuckDB ext
- **Railway volume + DuckDB binary + Bun HTTP wrapper** — DuckDB-native, ~$1-3/mo
- **MotherDuck** — hosted DuckDB, free 10GB tier, zero infra
- **S3 + parquet** — `read_parquet('s3://...')`, no server

## Retention notes

CC default `cleanupPeriodDays` ~30. To keep longer history: set in `~/.claude/settings.json`:
```json
"cleanupPeriodDays": 365
```
or `0` for never. Worth bumping now so we have more data to mine when prototyping.

## Calibration run (2026-04-27, 3 sessions from 2026-04-26)

Sessions picked by total_billable_in:

| session_id | msgs | tokens | cache hit | duration |
|---|---|---|---|---|
| 011dcfcb | 343 | 82M | 92% | 158min |
| cfbd10a6 | 340 | 78M | 98% | 108min |
| 38499184 | 296 | 35M | 92% | 1282min |

**Signal confirmed.** ~15-20 friction moments per session, repeats hold across all 3.

### Friction taxonomy (v0)

| Type | Example evidence | Heuristic |
|---|---|---|
| **Copy clarity** | "what do you mean call out overrides", "apply all i don't follow", "ahh 328 is issue not pr" | regex `i don.t (follow\|understand)\|what.*mean\|huh\?` in user msg |
| **Re-asking** | 10x "yes" / 5x "y" in single session - model asks "want me to X?" after established pref | short user msg `^(yes\|y\|do it\|go\|ok)$` after assistant Q ending in `?` |
| **Hard interrupt** | `[Request interrupted by user]` | exact string match |
| **Stall** | "319 PR took 5 min with no clear progress", "why did 319 take so long" | user msg w/ time-reference + "no progress\|too long\|slow" |
| **Drift / rule violation** | "reminder we don't work in sprints" (already CLAUDE.md rule) | user msg `(reminder\|don't\|stop)` + repo CLAUDE.md keyword |
| **Status begging** | "status 336?", "what's in 334", "status of qa stories" | regex `\bstatus\b\s*\d+\|what.s in\s+\d+` |

### Tool: `cc-friction-peek <session_id>`

Lives at `bin/cc-friction-peek`. Prints user msgs, tool sequences, top-output assistant msgs. Hardcoded to preach-hub project dir for now (calibration). Run as: `cc-friction-peek <uuid>`.

## Next concrete step

Build a heuristic-only friction scanner: walk last 7d sessions, apply taxonomy regexes, output top-N candidates ranked by recurrence x severity. **No LLM yet.** If heuristics alone give actionable signal, wrap in skill. If too noisy, add LLM classifier on filtered candidates.

Promote winners through `/systematize`:
- Re-asking pattern: already in CLAUDE.md output discipline rule #4. Need PreToolUse hook gating "want me to" / "should I" in assistant text? Or compile prompt example reinforcement.
- Drift on no-sprints rule: CLAUDE.md exists, model still violates. Hook on assistant output catching banned phrases?
- Copy clarity in skills: audit skill text against confused phrasings. `/qa-triage` "apply all" / "call out overrides" specific.
