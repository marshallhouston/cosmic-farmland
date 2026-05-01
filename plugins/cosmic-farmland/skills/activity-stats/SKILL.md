---
name: activity-stats
description: "Generate wall-clock active work stats for the current repo by combining git commits + Claude Code session events. Produces weekly hours summary, day x 4h-bucket heatmap (HTML), and a paste-ready prompt. Use when the user says /activity-stats, 'how many hours did I work', 'activity report', 'weekly hours', 'time spent on this repo', or wants to share progress with a co-founder/cowork."
argument-hint: "[author-substring] (default: marshall) [tz] (default: America/Denver)"
---

# /activity-stats — wall-clock active work report

Produces:
1. Weekly hours table (5 / 10 / 20 min gap thresholds)
2. Day x 4-hour-bucket HTML heatmap
3. Paste-ready prompt copied to clipboard for sharing with Cowork / Tyler / Slack

## When to use

- `/activity-stats`
- "how many hours did I work on X"
- "activity report" / "weekly hours" / "time spent"
- "share progress with cowork" / "tell tyler how much I worked"
- Pre-Tyler-update prep ("how much have I shipped this week?")

## What it measures

Wall-clock active work — NOT commits, NOT lines-of-code.

Activity events = `git log` author timestamps + Claude Code session jsonl
timestamps from `~/.claude/projects/<repo-slug>*/`. Events merged into
intervals using a gap threshold; gaps larger than threshold = break.
Three thresholds shown side-by-side (5/10/20 min) so the user sees how
sensitive the number is to the cutoff.

## Steps

1. Confirm cwd is a git repo. If not, `git rev-parse` will fail — bail
   with a one-line error explaining this is repo-scoped.

2. Resolve author substring: arg if provided, else default to
   `marshall`. Confirm matches with
   `git log --pretty='%an' | sort -u | grep -i <author>`. If zero
   matches, list candidates and stop.

3. Locate scripts. Two places to check, in order:
   - `scripts/stats/` in current repo (preach-hub canonical)
   - Fallback: prompt user that scripts aren't installed in this repo
     and offer to copy them from `~/code/preach-hub/scripts/stats/`

4. Run `scripts/stats/heatmap.sh <author>` — produces
   `docs/stats/heatmap.html` and prints totals (5min, 10min, 20min).
   Output will look like:
   ```
   Wrote docs/stats/heatmap.html with 3 tabs (5min, 10min, 20min)
       5min:  91.2h  intervals=279
      10min: 102.1h  intervals=187
      20min: 115.4h  intervals=131
   ```
   Capture the three totals.

5. Pull weekly breakdown — re-run the python block inside `heatmap.sh`
   OR parse the generated HTML's summary table. Easiest: have the
   script print weekly numbers to stdout (extend if needed). For now,
   read them from the HTML's `<table class="summary">` rows.

6. Pull date range:
   - First: `git log --author=<author> --reverse --pretty='%ad' --date=short | head -1`
   - Last: `git log --author=<author> --pretty='%ad' --date=short | head -1`
   - Active days: count unique dates from `--pretty='%ad' --date=short | sort -u | wc -l`

7. Build the paste-ready summary in this exact shape (preserve format
   so it threads cleanly with prior reports):

   ```
   Updated <repo> activity stats for <author>, <first> -> <last>.

   Method: union of git commit timestamps + Claude Code session events
   (<N>+ events from <M> session files), merged with gap thresholds
   (5/10/20 min) into continuous work intervals, allocated to local-tz
   days. Measures wall-clock active work, not commits or LOC.

   Weekly hours by gap threshold (strict / middle / generous):

     Week       5min   10min   20min   Notes
     <yyyy>-W<nn>   ...   ...    ...    [partial / peak]
     ...
     ---------  -----  -----   -----
     Total      <a>    <b>     <c>

   <D> active days. Avg <x>-<y>h/day depending on threshold.

   Caveats: offline thinking, doc reading in browser, meetings, paper
   sketching, and parallel-thread work all under-counted. Real time
   invested is meaningfully higher than shown.

   Source: <repo> repo, branch <current-branch>
     scripts/stats/heatmap.sh         -- generates docs/stats/heatmap.html
     scripts/stats/daily-active.sh    -- terminal per-day report
     scripts/stats/concurrency.sh     -- PR/branch overlap
     scripts/stats/concurrency-commits.sh -- commit-window concurrency

   Please update the relevant tracker / dashboard with these figures.
   ```

8. Pipe to `pbcopy`. Confirm with `pbpaste | wc -l`.

9. Open the HTML: `open docs/stats/heatmap.html`.

10. Report to user:
    - Three totals (5/10/20 hours)
    - Active days, avg/day band
    - "Copied N-line summary to clipboard. Heatmap opened."
    - Don't dump the full pasted text back at the user — they have
      the clipboard. Just confirm.

## Caveats to surface (only if user asks "is this accurate")

- Offline thinking, doc reading in browser, meetings, paper sketching
  invisible.
- Screen-staring without typing or AI activity > gap threshold = not
  counted.
- Parallel-thread work counted as wall-clock once, not effort.
- Day cutoff is local tz; midnight-crossing sessions split.
- Some Claude Code session timestamps include automated background
  activity (small inflation).
- Single-repo view; doesn't account for other projects, planning,
  writing, or calls tied to the same work.

## Don't

- Don't run on a repo that doesn't have `scripts/stats/` installed
  without first asking — the user may not want auto-install.
- Don't include commits / LOC / words in the summary unless user
  explicitly asks. Past iteration of this report had them; user
  removed them as too much info.
- Don't post to Slack / email / GitHub automatically. Clipboard +
  HTML open is the contract; user pastes manually.
- Don't recompute via a different methodology. The 5/10/20 gap-merge
  model with commits + Claude session timestamps is the canonical
  measure — changing it breaks comparability with prior reports.
