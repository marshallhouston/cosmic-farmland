---
name: skill-stats
description: "Cross-project Claude Code skill-usage report from session transcripts. Counts every Skill invocation across ~/.claude/projects (all history, real names, normalized bare-vs-namespaced), by skill / project / session / day. Use when the user says /skill-stats, 'which skills do I use', 'skill usage', 'am I using skill X', 'dead skills', 'what skills never fire', or wants to prune their skill library. Pairs with the Honeycomb 'Skill Usage' board (live trigger mix + token cost)."
argument-hint: "[days] (default: all history) [skill-substring] (filter)"
---

# /skill-stats — skill usage from transcripts

Counts every `Skill` tool invocation across ALL Claude Code projects on this
machine, straight from the session JSONL. Retroactive, zero infra, real names
(no OTel redaction). Complements the Honeycomb **Skill Usage** board, which is
live but only un-redacts your own skills after `OTEL_LOG_TOOL_DETAILS=1` (set
2026-05-29) and is the source of truth for **trigger mix** and **token/$ cost**.

## When to use

- `/skill-stats` — full report
- "which skills do I actually use" / "skill usage" / "am I using X"
- "dead skills" / "what never fires" — prune candidates
- Before editing/removing a skill, to check real adoption

## What it measures (and what it can't)

- **Can:** invocation count per skill, distinct sessions + projects, first/last
  seen, full history. Names are verbatim (transcripts aren't redacted).
- **Can't:** trigger type (transcripts log every call `caller.type:"direct"` —
  proactive vs slash vs nested only exists in OTel) and token/$ cost. For those,
  open the Honeycomb board (link in step 5).

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

5. Point to the live view for the dimensions transcripts can't give:
   > Trigger mix (proactive/slash/nested) + token + $ cost per skill:
   > Honeycomb board "Skill Usage" — https://ui.honeycomb.io/justpreach.app/environments/production/datasets/claude-code

6. Keep output tight. Ranked table + headline + (if asked) prune list. Don't
   dump per-session detail unless asked.

## Don't

- Don't write any file or open a browser unless the user asks — this is a
  read-only report by default.
- Don't conflate with the Honeycomb board's numbers: transcripts count *every*
  Skill tool call with real names over all history; the board counts
  `skill_activated` events (redacted pre-flag) and is the only source for
  trigger + cost. They will not match exactly, by design.
- Don't recommend deleting a skill on count alone — a rarely-used skill may be
  high-value (e.g. an incident runbook). Flag, don't prescribe.
- Don't normalize away the plugin namespace silently — note `[namespaced+bare]`
  when a skill was invoked both ways (e.g. `ship` and `cosmic-farmland:ship`),
  so the user knows the count is merged.
