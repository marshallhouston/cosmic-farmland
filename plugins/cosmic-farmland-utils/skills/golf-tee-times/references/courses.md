# Course reference

The authoritative course list lives in `courses.json`. This file is prose notes about each platform's quirks, learned by trial and error.

## CPS Golf (Club Prophet Systems)

Courses: Westminster, Indian Tree, West Woods.

- Search page: `https://{subdomain}.cps.golf/onlineresweb/search-teetime`
- URL params that work: `NumberOfPlayer`, `TeeOffTimeMin`, `TeeOffTimeMax` (values are integer hours, 7 and 10 work).
- `SearchDate` URL param does **not** stick — you have to click the day in the calendar after the page loads.
- Calendar: dates render as `<div class="day-unit">N</div>`. Click via `document.querySelectorAll('div.day-unit')` and match on `textContent === '11'`.
- "No tee times available" is shown as literal text.
- Tee-time cards follow this text pattern: `"{time}{course}Tee{teeNum} 18 HOLES | {playerRange} GOLFERS Book Now"`.
- West Woods requires login before showing the search page at all — redirects to an email-entry page.

## TeeItUp

Courses: Hyland Hills, Common Ground, Riverdale.

- Page: `https://{subdomain}.book.teeitup.com/?date=YYYY-MM-DD&holes=18&max=999999`
- The `date` URL param **does** stick — no calendar click needed.
- Each tee time renders `X:XX AM` / `X:XX PM` in its own element. Easiest extraction: grab all elements whose textContent matches `/^\d{1,2}:\d{2}\s?(AM|PM)$/`.
- Common Ground needs `&course=5275` in the URL.

## MemberSports

Courses: Denver Muni (org 3831), Foothills (org 3697), Broken Tee Englewood (org 3689).

- Page: `https://app.membersports.com/tee-times/{org_id}/{facility_id}/0/{?}/0`
- Angular Material calendar. Open via `document.querySelector('button[aria-label="Open calendar"]').click()`, wait ~800ms, then click the right cell via `document.querySelectorAll('.mat-calendar-body-cell')` matching `aria-label === "April 11, 2026"`.
- After clicking, wait ~2.5 seconds for results to load.
- Results appear as text lines: time, course, player range, price, repeating. Parse by walking lines and tracking the most recent time.
- **Denver courses at 3831/4928 are all Par 3 / 9-hole in the morning** — the real 18-hole courses (Wellshire, City Park, etc.) rarely show mornings here. Their 18-hole listings live in a different MemberSports view or may not be book-ahead at all for singles.
- **Foothills "Foothills 18 Back Nine"** means starting on hole 10 and playing 9 holes (not 18). "Foothills 18" means an actual 18-hole round.
- **Broken Tee "Championship"** is the 18-hole course; "Par 3" is par 3.
- Aerification dates to watch: Foothills Apr 13–16 (Apr 11 is fine), Wellshire/City Park Apr 13–14, Harvard Gulch Apr 15, Willis Case Apr 20–21, Kennedy Apr 20–23.

## ClubCaddie

Course: Applewood.

- Direct slot endpoint: `https://apimanager-cc11.clubcaddie.com/webapi/view/hbfdabab/slots?date=MM%2FDD%2FYYYY&player=N&ratetype=any`
- Date format in URL is URL-encoded `MM/DD/YYYY`. April 11, 2026 = `04%2F11%2F2026`.
- `player` must be 1, 2, 3, or 4.
- Returns an HTML page that renders tee times inline as course name, time, price, "18 Holes", "Book Now".
- Applewood has an "Applewood GC - Front" sub-label on each slot.

## EZLinks

Course: City of Aurora.

- Page: `https://cityofaurora.ezlinksgolf.com/index.html#/search`
- **Protected by Cloudflare bot-check.** The Chrome MCP tab group fails the check because it's flagged as automation. Marshall's regular Chrome tab passes. The MCP tab and the user tab do **not** share cookies.
- Filter form is Angular with jQuery datepicker, not scriptable via simple DOM manipulation.
- Current workaround: ask marshall to set filters in his logged-in tab and paste the results, or use computer-use on the existing tab.
- Aurora's 18-hole courses: Aurora Hills, Meadow Hills, Murphy Creek, Saddle Rock, Springhill. Entries prefixed "~ Back 9" are 9-hole rounds, not 18 — ignore for 18-hole searches.
