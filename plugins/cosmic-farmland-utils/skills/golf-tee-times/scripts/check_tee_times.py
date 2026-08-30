#!/usr/bin/env python3
"""
Check tee times across marshall's bookmarked golf courses.

Covers the platforms with discovered public APIs:
  - CPS Golf (Westminster, Indian Tree)
  - TeeItUp (Hyland Hills, Common Ground, Riverdale)
  - ClubCaddie (Applewood)

Platforms that need the browser instead (handled by Claude using Chrome MCP
when this script flags them as "browser_required"):
  - MemberSports (Denver muni, Foothills, Broken Tee) - POST endpoint with
    body that we haven't fully reverse-engineered yet
  - CPS Golf West Woods - requires login cookie
  - EZLinks City of Aurora - Cloudflare bot-check

Usage:
    python check_tee_times.py --date 2026-04-11 --players 1 \
        --start 07:00 --end 10:00 --holes 18
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    sys.stderr.write(
        "Need the 'requests' package. Install with: "
        "pip install requests --break-system-packages\n"
    )
    sys.exit(1)


# ---- Course config -----------------------------------------------------------

CPS_GOLF_COURSES = [
    # (pretty name, subdomain, courseIds query-string value)
    # courseIds is the comma-separated list of internal course IDs the site
    # uses to identify its sub-courses. Westminster has Walnut Creek + Legacy
    # Ridge bundled under one site; courseIds "1,4,2" was observed in the
    # live GetAllOptions response.
    ("Westminster (Walnut Creek / Legacy Ridge)", "cityofwestminster", "1,4,2"),
    ("Indian Tree", "indiantree", None),  # will be auto-discovered
]

TEEITUP_COURSES = [
    # (pretty name, facilityId, site subdomain for building book URL)
    ("Hyland Hills", 9201, "hyland-hills-park-recreation-district"),
    ("Common Ground", 5275, "commonground-golf-course"),
    ("Riverdale", 1016, "riverdale"),
]

CLUBCADDIE_COURSES = [
    # (pretty name, view_id)
    ("Applewood", "hbfdabab"),
]

BROWSER_REQUIRED = [
    ("Denver Muni (Wellshire, City Park, Willis Case, Overland, Kennedy)",
     "membersports", "https://app.membersports.com/tee-times/3831/4928/0/1/0"),
    ("Foothills (Foothills GC, Meadows)",
     "membersports", "https://app.membersports.com/tee-times/3697/4759/0/3/false"),
    ("Broken Tee Englewood",
     "membersports", "https://app.membersports.com/tee-times/3689/4748/0/0/0"),
    ("West Woods", "cps-golf-login",
     "https://westwoodsarvada.cps.golf/onlineresweb/search-teetime"),
    ("City of Aurora (Aurora Hills, Meadow Hills, Murphy Creek, Saddle Rock, Springhill)",
     "ezlinks", "https://cityofaurora.ezlinksgolf.com/index.html#/search"),
]


# ---- Result structures -------------------------------------------------------

@dataclass
class TeeTime:
    course: str           # top-level course (e.g. "Hyland Hills")
    sub_course: str       # more specific (e.g. "Gold Course" or "Walnut Creek Tee10")
    time: str             # "08:20 AM"
    price: str            # "$57.00" or "$33-$61"
    players_min: int
    players_max: int
    holes: int
    raw_source: str       # platform name for debugging


@dataclass
class CourseResult:
    course: str
    platform: str
    status: str           # "ok", "empty", "error", "browser_required"
    tee_times: List[TeeTime] = field(default_factory=list)
    note: str = ""


# ---- CPS Golf ----------------------------------------------------------------

def _cps_fetch_course_ids(subdomain: str) -> str:
    """Discover the comma-separated courseIds for a CPS Golf site."""
    url = (f"https://{subdomain}.cps.golf/onlineres/onlineapi/api/v1/"
           f"onlinereservation/GetAllOptions/{subdomain}")
    try:
        r = requests.get(url, params={"version": "25.3.4.21239412485", "product": 3}, timeout=10)
        data = r.json()
    except Exception:
        return ""
    # Look for a list of courses; field names vary but usually something like
    # "ListCourse" or "Courses". Be forgiving.
    for key in ("ListCourse", "Courses", "listCourse", "courses"):
        if key in data and isinstance(data[key], list):
            ids = [str(c.get("Id") or c.get("id") or c.get("CourseId")) for c in data[key]]
            ids = [i for i in ids if i and i != "None"]
            return ",".join(ids)
    return ""


def check_cps_golf(pretty_name: str, subdomain: str, course_ids: Optional[str],
                   date_str: str, players: int, start_hour: int, end_hour: int,
                   holes: int) -> CourseResult:
    """
    Hit the CPS Golf public TeeTimes endpoint.
    Observed endpoint:
      GET /onlineres/onlineapi/api/v1/onlinereservation/TeeTimes
          ?searchDate=Sat Apr 11 2026
          &holes=18
          &numberOfPlayer=1
          &courseIds=1,4,2
          &teeOffTimeMin=7
          &teeOffTimeMax=10
          &searchTimeType=0
          &teeSheetSearchView=5
          &classCode=R
          &defaultOnlineRate=N
          &isUseCapacityPricing=false
          &memberStoreId=1
          &searchType=1
    """
    if not course_ids:
        course_ids = _cps_fetch_course_ids(subdomain)
    if not course_ids:
        return CourseResult(pretty_name, "cps-golf", "error",
                            note="could not discover courseIds")

    # searchDate format: "Sat Apr 11 2026"
    d = datetime.strptime(date_str, "%Y-%m-%d")
    search_date = d.strftime("%a %b %d %Y")

    params = {
        "searchDate": search_date,
        "holes": holes,
        "numberOfPlayer": players,
        "courseIds": course_ids,
        "searchTimeType": 0,
        "teeOffTimeMin": start_hour,
        "teeOffTimeMax": end_hour,
        "isChangeTeeOffTime": "true",
        "teeSheetSearchView": 5,
        "classCode": "R",
        "defaultOnlineRate": "N",
        "isUseCapacityPricing": "false",
        "memberStoreId": 1,
        "searchType": 1,
    }
    url = (f"https://{subdomain}.cps.golf/onlineres/onlineapi/api/v1/"
           f"onlinereservation/TeeTimes")
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200 or not r.text.strip():
            return CourseResult(pretty_name, "cps-golf", "empty")
        data = r.json()
    except Exception as e:
        return CourseResult(pretty_name, "cps-golf", "error", note=str(e))

    # Response is typically a list of slot objects.
    slots = data if isinstance(data, list) else data.get("TeeTimes", [])
    tee_times = []
    for s in slots:
        # Field names vary; try common ones
        time_str = s.get("StartTimeDisplay") or s.get("StartTime") or s.get("TeeTime") or ""
        course_name = s.get("CourseName") or s.get("courseName") or ""
        min_p = s.get("MinPlayer") or s.get("minPlayer") or s.get("MinPlayers") or players
        max_p = s.get("MaxPlayer") or s.get("maxPlayer") or s.get("MaxPlayers") or players
        price = s.get("ShItemPriceDisplay") or s.get("RateDisplay") or s.get("Price") or ""
        holes_val = s.get("Holes") or holes
        tee_times.append(TeeTime(
            course=pretty_name,
            sub_course=str(course_name),
            time=str(time_str),
            price=str(price),
            players_min=int(min_p) if min_p else players,
            players_max=int(max_p) if max_p else players,
            holes=int(holes_val) if holes_val else holes,
            raw_source="cps-golf",
        ))

    status = "ok" if tee_times else "empty"
    return CourseResult(pretty_name, "cps-golf", status, tee_times=tee_times)


# ---- TeeItUp -----------------------------------------------------------------

def check_teeitup(pretty_name: str, facility_id: int, subdomain: str,
                  date_str: str, players: int, start_hour: int, end_hour: int,
                  holes: int) -> CourseResult:
    """
    TeeItUp backend lives at phx-api-be-east-1b.kenna.io.
    Observed endpoint:
      GET /v2/tee-times?date=2026-04-11&facilityIds=9201&returnPromotedRates=true
    Returns a JSON array of tee-time objects.
    """
    url = "https://phx-api-be-east-1b.kenna.io/v2/tee-times"
    params = {
        "date": date_str,
        "facilityIds": facility_id,
        "returnPromotedRates": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=15,
                         headers={"x-be-alias": subdomain})
        if r.status_code != 200:
            return CourseResult(pretty_name, "teeitup", "error",
                                note=f"http {r.status_code}")
        data = r.json()
    except Exception as e:
        return CourseResult(pretty_name, "teeitup", "error", note=str(e))

    # Response shape: list of tee times, each with time, course info, rates
    slots = data if isinstance(data, list) else data.get("teeTimes", [])
    tee_times = []
    for s in slots:
        time_iso = s.get("time") or s.get("teeTime") or ""
        # Time is "2026-04-11T08:20:00" local; parse the HH:MM part
        try:
            dt = datetime.fromisoformat(time_iso.replace("Z", ""))
            t_hour = dt.hour
            time_display = dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            continue
        if t_hour < start_hour or t_hour > end_hour:
            continue

        slot_holes = s.get("holes") or s.get("availableHoles") or holes
        if isinstance(slot_holes, list) and slot_holes:
            slot_holes = max(slot_holes)
        try:
            slot_holes_int = int(slot_holes)
        except Exception:
            slot_holes_int = holes
        if slot_holes_int != holes:
            continue

        min_p = s.get("minPlayers") or players
        max_p = s.get("maxPlayers") or s.get("playersAvailable") or players
        if int(max_p) < players:
            continue

        rates = s.get("rates") or []
        if rates:
            prices = [r.get("greenFeeWalking") or r.get("rate") or
                      r.get("price") or 0 for r in rates]
            prices = [p for p in prices if p]
            price_display = (f"${min(prices):.2f}"
                             + (f"–${max(prices):.2f}" if min(prices) != max(prices) else "")
                             if prices else "")
        else:
            price_display = ""

        course_name = (s.get("courseName")
                       or s.get("course", {}).get("name", "")
                       or pretty_name)

        tee_times.append(TeeTime(
            course=pretty_name,
            sub_course=course_name,
            time=time_display,
            price=price_display,
            players_min=int(min_p),
            players_max=int(max_p),
            holes=slot_holes_int,
            raw_source="teeitup",
        ))

    status = "ok" if tee_times else "empty"
    return CourseResult(pretty_name, "teeitup", status, tee_times=tee_times)


# ---- ClubCaddie (Applewood) --------------------------------------------------

def check_clubcaddie(pretty_name: str, view_id: str,
                     date_str: str, players: int, start_hour: int, end_hour: int,
                     holes: int) -> CourseResult:
    """
    ClubCaddie serves slots as an HTML fragment we parse with regex.
    URL: /webapi/view/{view_id}/slots?date=MM/DD/YYYY&player=N&ratetype=any
    """
    import re

    d = datetime.strptime(date_str, "%Y-%m-%d")
    mmddyyyy = d.strftime("%m/%d/%Y")
    url = f"https://apimanager-cc11.clubcaddie.com/webapi/view/{view_id}/slots"
    params = {"date": mmddyyyy, "player": players, "ratetype": "any"}

    try:
        r = requests.get(url, params=params, timeout=15)
        html = r.text
    except Exception as e:
        return CourseResult(pretty_name, "clubcaddie", "error", note=str(e))

    # Slot pattern: "Golfers: X - Y | <course>\n<sub-course>\nHH:MM AM\n$NN.NN\nN Holes"
    # Simpler: find repeating blocks where a time line is followed by price
    # and "N Holes".
    slot_re = re.compile(
        r"Golfers?:\s*(\d+)(?:\s*-\s*(\d+))?\s*([^\n]*?)\n"
        r"(\d{1,2}:\d{2}\s*[AP]M)\s*\n"
        r"\$([\d.]+)\s*\n"
        r"(\d+)\s*Holes",
        re.IGNORECASE,
    )
    tee_times = []
    for m in slot_re.finditer(html):
        min_p = int(m.group(1))
        max_p = int(m.group(2)) if m.group(2) else min_p
        sub = (m.group(3) or "").strip()
        time_str = m.group(4)
        price = f"${m.group(5)}"
        slot_holes = int(m.group(6))

        if slot_holes != holes:
            continue
        # Parse hour
        try:
            t_hour = datetime.strptime(time_str, "%I:%M %p").hour
        except Exception:
            continue
        if t_hour < start_hour or t_hour > end_hour:
            continue
        if max_p < players:
            continue

        tee_times.append(TeeTime(
            course=pretty_name,
            sub_course=sub,
            time=time_str,
            price=price,
            players_min=min_p,
            players_max=max_p,
            holes=slot_holes,
            raw_source="clubcaddie",
        ))

    status = "ok" if tee_times else "empty"
    return CourseResult(pretty_name, "clubcaddie", status, tee_times=tee_times)


# ---- Main --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--players", type=int, default=1)
    p.add_argument("--start", default="07:00", help="HH:MM earliest tee time")
    p.add_argument("--end", default="10:00", help="HH:MM latest tee time")
    p.add_argument("--holes", type=int, default=18)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = p.parse_args()

    start_hour = int(args.start.split(":")[0])
    end_hour = int(args.end.split(":")[0])

    results: List[CourseResult] = []

    # CPS Golf
    for pretty, sub, ids in CPS_GOLF_COURSES:
        results.append(check_cps_golf(
            pretty, sub, ids, args.date, args.players,
            start_hour, end_hour, args.holes,
        ))

    # TeeItUp
    for pretty, fid, sub in TEEITUP_COURSES:
        results.append(check_teeitup(
            pretty, fid, sub, args.date, args.players,
            start_hour, end_hour, args.holes,
        ))

    # ClubCaddie
    for pretty, vid in CLUBCADDIE_COURSES:
        results.append(check_clubcaddie(
            pretty, vid, args.date, args.players,
            start_hour, end_hour, args.holes,
        ))

    # Browser-required stubs
    for pretty, platform, url in BROWSER_REQUIRED:
        results.append(CourseResult(
            course=pretty,
            platform=platform,
            status="browser_required",
            note=f"Check manually via Chrome MCP: {url}",
        ))

    if args.json:
        out = [asdict(r) for r in results]
        print(json.dumps(out, indent=2, default=str))
        return

    # Text output
    print(f"Tee times · {args.date} · {args.players} player(s) · "
          f"{args.start}–{args.end} · {args.holes} holes\n")

    available = [r for r in results if r.status == "ok"]
    empty = [r for r in results if r.status == "empty"]
    browser = [r for r in results if r.status == "browser_required"]
    errors = [r for r in results if r.status == "error"]

    if available:
        print("Available:")
        for r in available:
            for tt in r.tee_times:
                sub = f" ({tt.sub_course})" if tt.sub_course else ""
                price = f"  {tt.price}" if tt.price else ""
                print(f"  {tt.time:<10} {r.course}{sub}"
                      f"{price}  {tt.players_min}–{tt.players_max} players")
        print()

    if empty:
        print("No availability in window:")
        for r in empty:
            print(f"  · {r.course}")
        print()

    if browser:
        print("Need browser (not hit by this script):")
        for r in browser:
            print(f"  · {r.course}")
        print()

    if errors:
        print("Errors:")
        for r in errors:
            print(f"  · {r.course}: {r.note}")


if __name__ == "__main__":
    main()
