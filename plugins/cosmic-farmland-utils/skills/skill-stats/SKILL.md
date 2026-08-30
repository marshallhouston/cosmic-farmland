---
name: skill-stats
description: "Skill-usage report from session transcripts, every project, all history. Triggers: /skill-stats, 'which skills do I use', 'dead skills', 'prune my skills'."
argument-hint: "[days] (default: all history) [skill-substring] (filter)"
---

# /skill-stats — skill usage from transcripts

Counts every `Skill` tool invocation across ALL Claude Code projects on this
machine, straight from the session JSONL. Retroactive, zero infra, real names
(no OTel redaction). Works standalone — no observability backend required.

If you also export Claude Code OTel to a backend (e.g. Honeycomb), that is the
source of truth for **trigger mix** and **token/$ cost** (transcripts can't give
those — see step 5). Skill names there are redacted to `custom_skill` unless you
set `OTEL_LOG_TOOL_DETAILS=1`.

## When to use

- `/skill-stats` — full report
- "which skills do I actually use" / "skill usage" / "am I using X"
- "dead skills" / "what never fires" — prune candidates
- Before editing/removing a skill, to check real adoption

## What it measures (and what it can't)

- **Can:** invocation count per skill, distinct sessions + projects, first/last
  seen, full history. Names are verbatim (transcripts aren't redacted).
- **Can't:** trigger type (transcripts log every call `caller.type:"direct"` —
  proactive vs slash vs nested only exists in OTel) and token/$ cost. Those
  need an OTel backend (see step 5); without one, this report is the full story.

## Steps

1. Resolve args: optional `days` (trailing window; default = all history) and
   optional `skill-substring` filter. No git/repo needed — this is global.

2. Run this inline (stdlib only, no deps):

   ```bash
   python3 - <<'PY'
   import json, glob, os, collections, datetime
   DAYS = None          # set to int N to window to trailing N days
   FILT = ""            # set to substring to filter skills
   cutoff = None
   if DAYS:
       cutoff = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=DAYS)).isoformat()

   def canon(s):        # normalize bare vs plugin-namespaced: cosmic-farmland:ship -> ship
       return s.split(":", 1)[1] if ":" in s else s

   cnt = collections.Counter()
   sess = collections.defaultdict(set)
   proj = collections.defaultdict(set)
   first, last = {}, {}
   raw_variants = collections.defaultdict(set)
   total_sessions, total_proj = set(), set()

   for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
       pj = os.path.basename(os.path.dirname(f))
       for line in open(f, errors="ignore"):
           if '"name":"Skill"' not in line:
               continue
           try: d = json.loads(line)
           except: continue
           ts = d.get("timestamp", "")
           if cutoff and ts and ts < cutoff:
               continue
           sid = d.get("sessionId")
           for b in d.get("message", {}).get("content", []):
               if isinstance(b, dict) and b.get("name") == "Skill":
                   raw = (b.get("input") or {}).get("skill", "?")
                   k = canon(raw)
                   if FILT and FILT.lower() not in k.lower():
                       continue
                   cnt[k] += 1
                   raw_variants[k].add(raw)
                   sess[k].add(sid); proj[k].add(pj)
                   total_sessions.add(sid); total_proj.add(pj)
                   if ts:
                       first[k] = min(first.get(k, ts), ts)
                       last[k]  = max(last.get(k, ts), ts)

   print(f"TOTAL: {sum(cnt.values())} invocations | "
         f"{len(cnt)} distinct skills | {len(total_sessions)} sessions | "
         f"{len(total_proj)} projects")
   print(f"{'count':>6}  {'sess':>4}  {'proj':>4}  {'last seen':<10}  skill")
   for k, c in cnt.most_common():
       fl = (last.get(k, "")[:10]) or "-"
       star = "  [namespaced+bare]" if len(raw_variants[k]) > 1 else ""
       print(f"{c:6}  {len(sess[k]):4}  {len(proj[k]):4}  {fl:<10}  {k}{star}")
   PY
   ```

   To window or filter, edit `DAYS` / `FILT` at the top before running.

3. Surface the headline: total invocations, distinct skills, sessions,
   projects, date span. Then the ranked table (top ~20; note how many tail
   skills have count 1-2 = prune candidates).

4. **Dead-skill check** (if user asked about pruning): cross-reference the
   installed skill list against the counts. Any skill that exists but has 0
   invocations (or only 1, long ago) is a prune candidate. List installed
   skills from the plugin/skill dirs and diff against `cnt` keys. Flag the
   gaps; do NOT delete anything — just report.

5. Point to the live view for the dimensions transcripts can't give —
   trigger mix (proactive/slash/nested) + token/$ cost per skill. These need
   Claude Code OTel export to an observability backend; the transcript report
   above needs none of that and works standalone.
   > If you export Claude Code OTel to your own Honeycomb, build a board over
   > the `claude-code` dataset grouped by skill for trigger mix + cost.
   > (Internal preach board, access-gated: https://ui.honeycomb.io/justpreach.app/environments/production/datasets/claude-code)

## OTel setup (optional — for the live trigger + cost half)

The transcript report needs none of this. To also get trigger mix + cost in
Honeycomb, three machine-local pieces (none can live in this repo — the first
two carry a personal API key / shell config):

1. **Exporter env** in `~/.claude/settings.json` (`env` block). Sends CC
   telemetry to your backend. Set `OTEL_LOG_TOOL_DETAILS=1` too:
   ```json
   "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
   "OTEL_METRICS_EXPORTER": "otlp",
   "OTEL_LOGS_EXPORTER": "otlp",
   "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
   "OTEL_EXPORTER_OTLP_ENDPOINT": "https://api.honeycomb.io",
   "OTEL_EXPORTER_OTLP_HEADERS": "x-honeycomb-team=<YOUR_KEY>",
   "OTEL_LOG_TOOL_DETAILS": "1"
   ```
   Do **not** put `OTEL_RESOURCE_ATTRIBUTES` here — settings env wins over the
   shell, which would clobber the per-repo `project` tag from step 2.

2. **Per-repo `project` tag** via a shell wrapper around `claude` (so worktrees
   fold to their main repo, not the suffixed dir):
   ```sh
   proj=$(basename "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")")
   case "$proj" in ""|.|/) proj=$(basename "$PWD") ;; esac
   export OTEL_RESOURCE_ATTRIBUTES="service.name=claude-code,project=$proj,user.id=<you>"
   ```

3. **Real names for local skills** come from the local transcripts, not from
   exported telemetry. CC redacts locally-sourced skill names (`skill.source` =
   userSettings / projectSettings / local plugin-dir) to `custom_skill` in OTel
   and exposes no `tool_use_id` to join the real name back, so the Honeycomb
   `claude-code` dataset is unreliable for local-skill names. This skill reads
   `~/.claude/projects/**/*.jsonl` directly (Anthropic already writes them to
   disk) where the real `skill` name is present in the `Skill` tool_input. No
   hook, no daemon, no key required. (A `skill-telemetry.py` PreToolUse hook
   posted real names to Honeycomb until 2026-06-17; removed once it had been
   posting nothing for weeks and the transcript path covered the same need.)

6. Keep output tight. Ranked table + headline + (if asked) prune list. Don't
   dump per-session detail unless asked.

## Don't

- Don't write any file or open a browser unless the user asks — this is a
  read-only report by default.
- Don't conflate with any OTel board's numbers: transcripts count *every*
  Skill tool call with real names over all history; an OTel board counts
  `skill_activated` events (redacted pre-flag) and is the only source for
  trigger + cost. They will not match exactly, by design.
- Don't recommend deleting a skill on count alone — a rarely-used skill may be
  high-value (e.g. an incident runbook). Flag, don't prescribe.
- Don't normalize away the plugin namespace silently — note `[namespaced+bare]`
  when a skill was invoked both ways (e.g. `ship` and `cosmic-farmland:ship`),
  so the user knows the count is merged.
