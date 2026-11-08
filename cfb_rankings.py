#!/usr/bin/env python3
"""
cfb_rankings.py — Alfred keywords: cfbr [poll], ncaafr [poll]
National FBS Polls:
  - Smart Default: College Football Playoff (CFP) Rankings when available, else AP Top 25
  - `cfbr cfp`     → College Football Playoff Rankings
  - `cfbr ap`      → AP Top 25 Poll
  - `cfbr coaches` → AFCA Coaches Poll (USA Today)
"""
from __future__ import annotations

import os
import sys

from utils import (
    alfred_error, alfred_output,
    api_get, cache_get, cache_get_stale, cache_set,
    TEAM_BY_ID, team_logo_path, WORKFLOW_DIR,
)

CACHE_TTL = 600  # 10 minutes
RANKINGS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"


def fetch_rankings_data() -> dict:
    key = "cfb_fbs_rankings"
    data = cache_get(key, CACHE_TTL)
    if data:
        return data

    stale = cache_get_stale(key)
    try:
        data = api_get(RANKINGS_URL)
        cache_set(key, data)
        return data
    except Exception:
        if stale:
            return stale
        raise


def _select_poll(rankings: list[dict], query: str) -> dict | None:
    q = query.lower().strip()
    by_type = {p.get("type", "").lower(): p for p in rankings if p.get("type")}

    if q in ("ap", "ap25", "ap top 25", "associated press"):
        return by_type.get("ap")
    if q in ("coaches", "coach", "afca", "usa"):
        return by_type.get("usa")
    if q in ("cfp", "playoff", "committee"):
        return by_type.get("cfp") or by_type.get("ap")

    # Smart default: CFP if available and non-empty, else AP Top 25, else Coaches
    cfp = by_type.get("cfp")
    if cfp and cfp.get("ranks"):
        return cfp
    return by_type.get("ap") or by_type.get("usa") or (rankings[0] if rankings else None)


def _format_trend(trend: str | None, current: int, previous: int) -> str:
    if previous and previous > 0:
        if previous == current:
            return "—"
        diff = previous - current
        return f"▲{diff}" if diff > 0 else f"▼{abs(diff)}"
    if previous == 0:
        return "—"
    if trend and trend != "-":
        if trend.startswith("+"):
            return f"▲{trend[1:]}"
        if trend.startswith("-"):
            return f"▼{trend[1:]}"
        return trend
    return "—"


def main():
    query = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    try:
        data = fetch_rankings_data()
    except Exception as e:
        alfred_error("Could not fetch NCAA FBS rankings", str(e))
        return

    rankings = data.get("rankings", [])
    poll = _select_poll(rankings, query)
    if not poll or not poll.get("ranks"):
        alfred_output([{
            "title": f"No FBS poll found for '{query}'",
            "subtitle": "Try: cfbr (default), cfbr cfp, cfbr ap, or cfbr coaches",
            "valid": False,
            "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")},
        }])
        return

    poll_name = poll.get("name", "Top 25 Rankings")
    occ_label = poll.get("occurrence", {}).get("displayValue", "")
    header_title = f"── {poll_name} ({occ_label}) ──" if occ_label else f"── {poll_name} ──"

    items = [{
        "title": header_title,
        "subtitle": "Switch poll: cfbr cfp · cfbr ap · cfbr coaches",
        "valid": False,
        "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")},
    }]

    for entry in poll.get("ranks", []):
        curr = entry.get("current", 0)
        prev = entry.get("previous", 0)
        team = entry.get("team", {})
        tid  = str(team.get("id", ""))
        loc  = team.get("location", "")
        nick = team.get("name", "")
        full_name = f"{loc} {nick}".strip() or TEAM_BY_ID.get(tid, {}).get("name", "Unknown")

        rec = entry.get("recordSummary", "")
        conf_short = TEAM_BY_ID.get(tid, {}).get("conference_short") or team.get("conferenceId", "FBS")
        trend_str = _format_trend(entry.get("trend"), curr, prev)
        pts = entry.get("points", 0)
        fpv = entry.get("firstPlaceVotes", 0)

        sub_parts = [f"Conf: {conf_short}", f"Trend: {trend_str}"]
        if prev and prev > 0:
            sub_parts.append(f"Prev: #{prev}")
        elif prev == 0:
            sub_parts.append("Prev: NR")
        if pts and float(pts) > 0:
            pts_str = f"Pts: {int(float(pts))}"
            if fpv and int(fpv) > 0:
                pts_str += f" ({int(fpv)} 1st-pl)"
            sub_parts.append(pts_str)

        clubhouse = f"https://www.espn.com/college-football/team/_/id/{tid}"
        title = f"#{curr} {full_name}  ({rec})" if rec else f"#{curr} {full_name}"

        items.append({
            "title": title,
            "subtitle": "  ·  ".join(sub_parts),
            "arg": clubhouse,
            "icon": {"path": team_logo_path(tid)},
            "mods": {
                "cmd": {
                    "subtitle": f"⌘ Open {full_name} Schedule on ESPN",
                    "arg": f"https://www.espn.com/college-football/team/schedule/_/id/{tid}",
                },
                "alt": {
                    "subtitle": f"⌥ Open {full_name} Stats on ESPN",
                    "arg": f"https://www.espn.com/college-football/team/stats/_/id/{tid}",
                },
            },
        })

    alfred_output(items)


if __name__ == "__main__":
    main()
