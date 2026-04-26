---
name: golf-tee-times
description: Check tee times across 11 Denver courses (CPS/TeeItUp/MemberSports/ClubCaddie/EZLinks), filtered by date/players/time/holes. Triggers: "tee times", "play golf", "when can I play", "find a round".
---

# Golf tee times

Marshall has 11 bookmarked Denver-area golf courses spanning five booking platforms. This skill checks all of them in one shot for a given date/time window/player count.

## Defaults (when marshall doesn't specify)

- **Players**: 1
- **Time window**: 7:00–10:00 AM (morning)
- **Holes**: 18
- **Walking/riding**: no preference

Always confirm the date — don't assume. If marshall says "Saturday" without a date, verify which Saturday.

## Step 1 — Try the Python script first

Run `scripts/check_tee_times.py` with the date, player count, earliest time, latest time, and hole count. It hits the known JSON endpoints for the four scriptable platforms (CPS Golf, TeeItUp, MemberSports, ClubCaddie) and returns a merged JSON blob.

```bash
python scripts/check_tee_times.py --date 2026-04-11 --players 1 --start 07:00 --end 10:00 --holes 18
```

The script covers 9 of the 11 courses. It will print results for:

- Westminster (Walnut Creek / Legacy Ridge) — CPS Golf
- Indian Tree — CPS Golf
- Westwoods — CPS Golf *(may require login cookie; see platform notes)*
- Hyland Hills — TeeItUp
- Common Ground — TeeItUp
- Riverdale — TeeItUp
- Denver Muni (Wellshire, City Park, Willis Case, Overland, Kennedy, Harvard Gulch) — MemberSports
- Foothills (Foothills GC, Meadows) — MemberSports
- Broken Tee Englewood — MemberSports
- Applewood — ClubCaddie

If the script returns results for everything it covers, skip to Step 3.

## Step 2 — Handle the browser-only courses

Two courses can't be hit via simple HTTP calls and need the browser (Chrome MCP):

### City of Aurora (EZLinks)

Aurora is behind a Cloudflare bot-check that fails inside the MCP tab group. The workaround: marshall must be logged in to the Aurora site in his regular Chrome tab **and** the Chrome MCP tab group must share that browser profile's cookies — which it does not by default. In practice: ask marshall to paste the filtered results, or use computer-use on his already-open tab via screenshots.

URL: `https://cityofaurora.ezlinksgolf.com/index.html#/search`

Aurora courses worth noting in results: Aurora Hills, Meadow Hills, Murphy Creek, Saddle Rock, Springhill. Ignore "~ Back 9" entries — those are 9-hole rounds, not 18.

### West Woods (CPS Golf, login-gated)

The Westwoods CPS Golf instance at `westwoodsarvada.cps.golf` requires an authenticated session even to view tee times. The MCP tab won't share cookies with marshall's logged-in tab. Same workaround as Aurora: computer-use on his open tab, or ask him to paste.

If marshall hasn't mentioned logging in, tell him upfront: "Aurora and Westwoods need you logged in — open them in Chrome and let me know, or paste the results."

## Step 3 — Present the results

Format as a table grouped by availability. Put courses **with** matching tee times first, then a compact "no availability" section. For each hit, show:

- Course name
- Time
- Sub-course if applicable (e.g. "Walnut Creek Tee10", "Applewood - Front")
- Price
- Player range (e.g. "1–4")

Example:

```
## Sat Apr 11, 2026 · 18 holes · 1 player · 7–10 AM

Available:
  8:40 AM   Aurora Hills         $37–$42   1–3 players
  8:42 AM   Saddle Rock          $33.50–$63   1–2 players

No morning availability:
  Westminster · Indian Tree · Hyland Hills · Common Ground ·
  Riverdale · Applewood · Foothills 18 · Broken Tee Championship ·
  Denver muni 18-holes

Couldn't check:
  West Woods (login required)
```

Keep the summary short. Marshall knows these courses and doesn't need them re-explained.

## Notes on the courses and their platforms

See `references/courses.md` for the full course list with URLs, platform quirks, and known aerification/closure dates.

## When single-player slots are rare

It's common for 1-player 18-hole slots to be hard to find, especially on weekend mornings — most booking sites prioritize 2-4 player groups, and solo slots get snapped up quickly. If nothing shows up, suggest:

1. Widening the window (e.g., 7 AM–noon)
2. Trying walk-ons at courses that accept them (Kennedy, Wellshire on Denver muni)
3. Booking a 2-player slot and showing up solo (allowed at most courses)
4. Checking again closer to the date — single-player slots open up as groups reshuffle

Don't suggest these unprompted on the first result; only mention them if the search genuinely returns nothing.

## Updating the course list

The course list lives in `references/courses.json`. If marshall adds or removes a bookmark, update it there.
