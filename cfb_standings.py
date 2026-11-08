#!/usr/bin/env python3
"""
cfb_standings.py — Alfred keywords: cfbs [conf], ncaafs [conf]
FBS Conference Standings ordered with Power 4 first, followed by Pac-12,
Group of 5 (including Sun Belt East/West sub-divisions), and FBS Independents.
Supports instant conference filtering (e.g. `cfbs sec`, `cfbs b10`, `cfbs b12`, `cfbs acc`).
"""
from __future__ import annotations

import os
import sys

from utils import (
    alfred_error, alfred_output,
    api_get, cache_get, cache_get_stale, cache_set,
    parse_standings_entry_stats, team_logo_path, WORKFLOW_DIR,
)

CACHE_TTL = 300  # 5 minutes
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/football/college-football/standings?group=80"

# Ordered list of FBS conference IDs and filter aliases (Power 4 first)
CONFERENCE_ORDER = [
    ("8",   "Southeastern Conference",   ["sec", "southeastern"]),
    ("5",   "Big Ten Conference",        ["b10", "big10", "big ten", "b1g"]),
    ("4",   "Big 12 Conference",         ["b12", "big12", "big 12"]),
    ("1",   "Atlantic Coast Conference", ["acc", "atlantic coast"]),
    ("9",   "Pac-12 Conference",         ["pac12", "pac-12", "pac 12", "pac"]),
    ("151", "American Conference",       ["aac", "american"]),
    ("17",  "Mountain West Conference",  ["mw", "mwc", "mwest", "mountain west"]),
    ("37",  "Sun Belt Conference",       ["sbc", "sun belt", "sunbelt", "belt"]),
    ("15",  "Mid-American Conference",   ["mac", "mid-american", "midam"]),
    ("12",  "Conference USA",            ["cusa", "c-usa", "conference usa", "usa"]),
    ("18",  "FBS Independents",          ["ind", "independent", "independents"]),
]


def header(title_str: str) -> dict:
    return {
        "title": f"── {title_str} ──",
        "subtitle": "",
        "valid": False,
        "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")},
    }


def team_item(rank: int, entry: dict) -> dict:
    team = entry.get("team", {})
    tid  = str(team.get("id", ""))
    name = team.get("displayName", "Unknown")
    st   = parse_standings_entry_stats(entry.get("stats", []))

    overall  = st["overall"]
    conf_rec = st["conf_rec"]
    diff     = st["diff"]
    streak   = st["streak"]
    pf       = st["pf"]
    pa       = st["pa"]
    vs_ap    = st["vs_ap"]

    clubhouse = f"https://www.espn.com/college-football/team/_/id/{tid}"
    for l in team.get("links", []):
        if "clubhouse" in l.get("rel", []):
            clubhouse = l.get("href", clubhouse)
            break

    subtitle = (
        f"{overall} (Conf: {conf_rec})  ·  Diff: {diff}  ·  "
        f"Streak: {streak}  ·  PF: {pf}  PA: {pa}  ·  vs Top 25: {vs_ap}"
    )

    return {
        "title": f"{rank}. {name}",
        "subtitle": subtitle,
        "arg": clubhouse,
        "icon": {"path": team_logo_path(tid)},
        "mods": {
            "cmd": {
                "subtitle": f"⌘ Open {name} Schedule on ESPN",
                "arg": f"https://www.espn.com/college-football/team/schedule/_/id/{tid}",
            },
            "alt": {
                "subtitle": f"⌥ Open {name} Stats on ESPN",
                "arg": f"https://www.espn.com/college-football/team/stats/_/id/{tid}",
            },
        },
    }


def fetch_standings_data() -> dict:
    key = "cfb_fbs_standings"
    data = cache_get(key, CACHE_TTL)
    if data:
        return data

    stale = cache_get_stale(key)
    try:
        data = api_get(STANDINGS_URL)
        cache_set(key, data)
        return data
    except Exception:
        if stale:
            return stale
        raise


def _matches_conf(query: str, conf_name: str, aliases: list[str]) -> bool:
    if not query:
        return True
    q = query.lower().strip()
    if q in conf_name.lower():
        return True
    return any(q == a or q in a for a in aliases)


def main():
    query = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    try:
        data = fetch_standings_data()
    except Exception as e:
        alfred_error("Could not fetch NCAA FBS standings", str(e))
        return

    conf_by_id: dict[str, dict] = {}
    for c in data.get("children", []):
        conf_by_id[str(c.get("id", ""))] = c

    items = []
    for cid, cname, aliases in CONFERENCE_ORDER:
        if not _matches_conf(query, cname, aliases):
            continue
        c_obj = conf_by_id.get(cid)
        if not c_obj:
            continue

        direct_entries = c_obj.get("standings", {}).get("entries", [])
        sub_children = c_obj.get("children", [])

        if direct_entries:
            items.append(header(cname))
            for rank, entry in enumerate(direct_entries, 1):
                items.append(team_item(rank, entry))
        elif sub_children:
            for sub in sub_children:
                sub_name = sub.get("name", cname)
                sub_entries = sub.get("standings", {}).get("entries", [])
                if sub_entries:
                    items.append(header(sub_name))
                    for rank, entry in enumerate(sub_entries, 1):
                        items.append(team_item(rank, entry))

    if not items:
        alfred_output([{
            "title": f"No FBS conference matching '{query}'",
            "subtitle": "Try: sec, b10, b12, acc, pac12, aac, mw, sbc, mac, cusa, or ind",
            "valid": False,
            "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")},
        }])
        return

    alfred_output(items)


if __name__ == "__main__":
    main()
