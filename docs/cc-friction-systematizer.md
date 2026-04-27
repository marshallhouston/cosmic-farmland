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

## Next concrete step

Pick 1 high-token session from yesterday, hand-craft friction-extraction prompt, eyeball output. No code yet. Validate signal exists before building pipeline.
