#!/usr/bin/env python3
"""
cfb_team.py — Alfred keywords: cfbt {query}, cfbc {query}, ncaaft {query}, ncaafc {query}
Unified Team Stats & 12-Game Schedule View:
  - Multi-match: Lists matching FBS teams with Season Record, ⌘ Offense stats, and ⌥ Defense stats.
  - Single-team match:
      Row 1     → Team Overview (Record, Conf Record, Streak, PF/PA, ⌘ Offense, ⌥ Defense)
      Rows 2..N → Full 12+ game season schedule inline (W/L results, live scores, upcoming kickoffs & TV)
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import (
    alfred_error, alfred_output,
    api_get, cache_get, cache_get_stale, cache_set,
    format_rank, get_curated_rank, matchup_icon_path,
    parse_standings_entry_stats, team_logo_path, TEAMS,
    utc_to_local, utc_to_short_date, WORKFLOW_DIR,
)

CACHE_TTL = 300  # 5 minutes
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/football/college-football/standings?group=80"


def search_teams(query: str) -> list[dict]:
    q = query.lower().strip()
    # Strip trailing 'schedule' or 'sched' if user typed `cfbt texas schedule`
    for suffix in (" schedule", " sched"):
        if q.endswith(suffix):
            q = q[:-len(suffix)].strip()

    if not q:
        return TEAMS

    # 1. Check for exact match on location, abbreviation, short_name, or full name
    exact = [
        t for t in TEAMS
        if q == t["location"].lower()
        or q == t["abbreviation"].lower()
        or q == t["name"].lower()
        or q == t.get("short_name", "").lower()
    ]
    if len(exact) == 1:
        return exact

    # 2. Substring match across name, location, nickname, abbreviation, or conference
    matches = []
    for t in TEAMS:
        if (
            q in t["name"].lower()
            or q in t["location"].lower()
            or q in t["nickname"].lower()
            or q in t["abbreviation"].lower()
            or q in t["conference"].lower()
            or q in t["conference_short"].lower()
            or any(q == a for a in t.get("conference_aliases", []))
        ):
            matches.append(t)
    return matches


def fetch_standings_map() -> dict[str, dict]:
    key = "cfb_fbs_standings"
    data = cache_get(key, CACHE_TTL) or cache_get_stale(key)
    if not data:
        try:
            data = api_get(STANDINGS_URL)
            cache_set(key, data)
        except Exception:
            return {}

    teams_map: dict[str, dict] = {}

    def _add_entries(entries: list[dict]):
        for entry in entries:
            t = entry.get("team", {})
            tid = str(t.get("id", ""))
            if tid:
                teams_map[tid] = parse_standings_entry_stats(entry.get("stats", []))

    for conf in data.get("children", []):
        _add_entries(conf.get("standings", {}).get("entries", []))
        for sub in conf.get("children", []):
            _add_entries(sub.get("standings", {}).get("entries", []))

    return teams_map


def fetch_team_stats(team_id: str) -> dict:
    key = f"cfb_team_stats_{team_id}"
    data = cache_get(key, CACHE_TTL) or cache_get_stale(key)
    if not data:
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/statistics"
        try:
            data = api_get(url)
            cache_set(key, data)
        except Exception:
            return {}

    categories = data.get("results", {}).get("stats", {}).get("categories", [])
    cat_map = {}
    for cat in categories:
        cname = cat.get("name")
        stats_dict = {}
        for s in cat.get("stats", []):
            stats_dict[s.get("name")] = s.get("displayValue")
        cat_map[cname] = stats_dict
    return cat_map


def fetch_team_schedule(team_id: str) -> dict:
    key = f"cfb_team_sched_{team_id}"
    data = cache_get(key, CACHE_TTL) or cache_get_stale(key)
    if not data:
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/schedule"
        try:
            data = api_get(url)
            cache_set(key, data)
        except Exception:
            return {}
    return data


def _extract_score_str(comp_entry: dict) -> str:
    sc = comp_entry.get("score")
    if isinstance(sc, dict):
        return str(sc.get("displayValue", int(sc.get("value", 0))))
    if sc is not None:
        return str(sc)
    return "0"


def _extract_broadcast_str(comp: dict) -> str:
    broadcasts = comp.get("broadcasts", [])
    if not broadcasts:
        return ""
    b0 = broadcasts[0]
    names = b0.get("names", [])
    if names:
        return names[0]
    media_name = b0.get("media", {}).get("shortName", "")
    return media_name


def build_team_item(team: dict, standings_map: dict[str, dict], fetch_detailed_stats: bool = True) -> dict:
    tid  = str(team["id"])
    name = team["name"]
    conf_short = team.get("conference_short", "FBS")
    std  = standings_map.get(tid, {})

    overall  = std.get("overall", "0-0")
    conf_rec = std.get("conf_rec", "0-0")
    diff     = std.get("diff", "0")
    streak   = std.get("streak", "—")
    pf       = std.get("pf", "0")
    pa       = std.get("pa", "0")
    vs_ap    = std.get("vs_ap", "0-0")

    subtitle = f"{overall} ({conf_rec} {conf_short}) · Diff: {diff} · Streak: {streak} · PF: {pf} · PA: {pa} · vs Top 25: {vs_ap}"
    clubhouse = f"https://www.espn.com/college-football/team/_/id/{tid}"
    stats_url = f"https://www.espn.com/college-football/team/stats/_/id/{tid}"

    if fetch_detailed_stats:
        team_stats = fetch_team_stats(tid)
        passing = team_stats.get("passing", {})
        rushing = team_stats.get("rushing", {})
        defensive = team_stats.get("defensive", {})
        scoring = team_stats.get("scoring", {})
        interceptions = team_stats.get("defensiveInterceptions", {})
        general = team_stats.get("general", {})

        pass_yds = passing.get("passingYards", "—")
        pass_tds = passing.get("passingTouchdowns", "—")
        cmp_pct  = passing.get("completionPct", "—")
        rush_yds = rushing.get("rushingYards", "—")
        rush_tds = rushing.get("rushingTouchdowns", "—")
        pts_pg   = scoring.get("totalPointsPerGame", "—")

        sacks       = defensive.get("sacks", "—")
        ints        = interceptions.get("interceptions", "—")
        forced_fumb = general.get("fumblesForced", "—")
        tot_tackles = defensive.get("totalTackles", "—")

        off_sub = f"⌘ Offense: {pts_pg} PPG · Pass: {pass_yds} YDS ({pass_tds} TD, {cmp_pct}%) · Rush: {rush_yds} YDS ({rush_tds} TD)"
        def_sub = f"⌥ Defense: {sacks} Sacks · {ints} INTs · {forced_fumb} Forced Fum · {tot_tackles} Tackles"
    else:
        off_sub = f"⌘ Open {name} Offensive Stats on ESPN"
        def_sub = f"⌥ Open {name} Defensive Stats on ESPN"

    return {
        "title": f"{name}  [{conf_short}]",
        "subtitle": subtitle,
        "arg": clubhouse,
        "icon": {"path": team_logo_path(tid)},
        "mods": {
            "cmd": {"subtitle": off_sub, "arg": stats_url},
            "alt": {"subtitle": def_sub, "arg": stats_url},
        },
    }


def build_schedule_items(team: dict) -> list[dict]:
    tid = str(team["id"])
    sched_data = fetch_team_schedule(tid)
    events = sched_data.get("events", [])
    if not events:
        return []

    items = [{
        "title": f"── {team['name']} Season Schedule ({len(events)} Games) ──",
        "subtitle": "Press Enter on any game to open Box Score / Gamecast on ESPN",
        "valid": False,
        "icon": {"path": team_logo_path(tid)},
    }]

    for ev in events:
        comp = ev.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        us = next((c for c in competitors if str(c.get("team", {}).get("id")) == tid), competitors[0])
        opp = next((c for c in competitors if str(c.get("team", {}).get("id")) != tid), competitors[-1])

        home_c = next((c for c in competitors if c.get("homeAway") == "home"), us)
        away_c = next((c for c in competitors if c.get("homeAway") == "away"), opp)
        away_id = str(away_c.get("team", {}).get("id", ""))
        home_id = str(home_c.get("team", {}).get("id", ""))

        is_home = us.get("homeAway") == "home"
        vs_at = "vs" if is_home else "@"
        opp_team = opp.get("team", {})
        opp_name = opp_team.get("shortDisplayName") or opp_team.get("displayName", "Opponent")
        opp_rank = format_rank(get_curated_rank(opp))

        wk_text = ev.get("week", {}).get("text", "")
        date_str = ev.get("date") or comp.get("date", "")
        short_date = utc_to_short_date(date_str)
        wk_prefix = f"{wk_text} ({short_date})" if wk_text and short_date else (wk_text or short_date or "Game")

        status = comp.get("status", {}).get("type", {})
        state = status.get("state", "pre")
        status_detail = status.get("shortDetail", status.get("detail", ""))

        eid = ev.get("id", "")
        gamecast_url = f"https://www.espn.com/college-football/game/_/gameId/{eid}"
        boxscore_url = f"https://www.espn.com/college-football/boxscore/_/gameId/{eid}"
        venue = comp.get("venue", {}).get("fullName", "")
        broadcast = _extract_broadcast_str(comp)

        icon_path = matchup_icon_path(away_id, home_id)

        if state == "post":
            our_score = _extract_score_str(us)
            opp_score = _extract_score_str(opp)
            won = us.get("winner", False)
            wl = "W" if won else "L"
            ot_suffix = " (OT)" if "OT" in status_detail else ""
            title = f"{wk_prefix}:  {wl} {our_score}-{opp_score}{ot_suffix}  {vs_at} {opp_rank}{opp_name}"
            sub_parts = [s for s in ["Final", venue] if s]
            url = boxscore_url
        elif state == "in":
            our_score = _extract_score_str(us)
            opp_score = _extract_score_str(opp)
            title = f"{wk_prefix}:  🔴 LIVE {our_score}-{opp_score}  {vs_at} {opp_rank}{opp_name}  — {status_detail}"
            sub_parts = [s for s in ["LIVE", venue, broadcast] if s]
            url = gamecast_url
        else:
            kickoff = utc_to_local(date_str, include_date=True)
            title = f"{wk_prefix}:  {vs_at} {opp_rank}{opp_name}  —  {kickoff}"
            sub_parts = [s for s in [venue, broadcast] if s]
            url = gamecast_url

        items.append({
            "title": title,
            "subtitle": " · ".join(sub_parts) if sub_parts else "Season Matchup",
            "arg": url,
            "icon": {"path": icon_path},
            "mods": {
                "cmd": {"subtitle": "⌘ Open Box Score", "arg": boxscore_url},
                "alt": {"subtitle": "⌥ Open Gamecast", "arg": gamecast_url},
            },
        })

    return items


def main():
    query = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    matched_teams = search_teams(query)

    if not matched_teams:
        alfred_output([{
            "title": f"No NCAA FBS teams matching '{query}'",
            "subtitle": "Try searching by school, nickname, abbreviation, or conference (e.g. texas, sec, osu)",
            "valid": False,
            "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")},
        }])
        return

    standings_map = fetch_standings_map()

    # Unified Single-Team View: Row 1 = Team Overview (⌘ Off / ⌥ Def), Rows 2..N = 12-Game Season Schedule
    if len(matched_teams) == 1:
        t = matched_teams[0]
        overview_item = build_team_item(t, standings_map, fetch_detailed_stats=True)
        sched_items = build_schedule_items(t)
        alfred_output([overview_item] + sched_items)
        return

    # Multi-team match: fetch detailed stats in parallel only if <= 8 teams matched
    subset = matched_teams[:20]
    fetch_detailed = len(subset) <= 8

    if fetch_detailed:
        order = {t["id"]: i for i, t in enumerate(subset)}
        built = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(build_team_item, t, standings_map, True): t for t in subset}
            for fut in as_completed(futs):
                built.append((futs[fut]["id"], fut.result()))
        built.sort(key=lambda x: order.get(x[0], 999))
        items = [item for _, item in built]
    else:
        items = [build_team_item(t, standings_map, fetch_detailed_stats=False) for t in subset]

    alfred_output(items)


if __name__ == "__main__":
    main()
