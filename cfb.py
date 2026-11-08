#!/usr/bin/env python3
"""
cfb.py — Alfred keywords: cfb, ncaaf
Single entry-point router and FBS Scoreboard module.

Boundary-aware routing (withspace: false):
  cfb / ncaaf              → All FBS games this week (Live → Upcoming → Final, Top 25 prioritized)
  cfb {filter}             → Filter scoreboard (e.g. `cfb texas`, `cfb sec`, `cfb top25`, `cfb close`, `cfb live`)
  cfbs [conf]              → FBS Conference Standings (Power 4 first, optional conference filter)
  cfbr [poll]              → National Polls (CFP default when out, AP Top 25 fallback, Coaches)
  cfbt [team] / cfbc [team]→ Unified Team Stats (⌘ Off / ⌥ Def) + Inline 12-Game Schedule
"""
from __future__ import annotations

import os
import sys

from utils import (
    alfred_error, alfred_output,
    api_get, cache_get, cache_get_stale, cache_set,
    format_rank, get_curated_rank, matchup_icon_path,
    TEAM_BY_ID, utc_to_local, WORKFLOW_DIR,
)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=300"
CACHE_TTL = 30
RERUN_LIVE = 5.0


def _is_subcommand(raw: str, prefix: str) -> bool:
    """
    True only when raw starts directly with `prefix` (no leading space) AND
    either equals `prefix` or is immediately followed by whitespace.
    """
    if not raw.startswith(prefix):
        return False
    rest = raw[len(prefix):]
    return rest == "" or rest[0].isspace()


def main():
    raw_query = sys.argv[1] if len(sys.argv) > 1 else ""
    raw_lower = raw_query.lower()

    # If the user did NOT type a leading space, check boundary-aware subcommands
    if raw_lower and not raw_lower[0].isspace():
        if _is_subcommand(raw_lower, "s"):
            arg = raw_query[1:].strip()
            sys.argv = [sys.argv[0], arg]
            from cfb_standings import main as standings_main
            standings_main()
            return

        if _is_subcommand(raw_lower, "r"):
            arg = raw_query[1:].strip()
            sys.argv = [sys.argv[0], arg]
            from cfb_rankings import main as rankings_main
            rankings_main()
            return

        if _is_subcommand(raw_lower, "t") or _is_subcommand(raw_lower, "c"):
            arg = raw_query[1:].strip()
            sys.argv = [sys.argv[0], arg]
            from cfb_team import main as team_main
            team_main()
            return

    # Otherwise: route to Scoreboard (with optional filter string)
    scores_main(raw_query.strip())


def _extract_leaders_summary(comp: dict) -> str:
    """Format Passing / Rushing / Receiving game leaders from competition payload."""
    parts = []
    label_map = {
        "passingYards": "Pass",
        "rushingYards": "Rush",
        "receivingYards": "Rec",
    }
    for cat in comp.get("leaders", []):
        cname = cat.get("name", "")
        short_lbl = label_map.get(cname)
        if not short_lbl:
            continue
        leaders_list = cat.get("leaders", [])
        if not leaders_list:
            continue
        top = leaders_list[0]
        athlete = top.get("athlete", {}).get("shortName") or top.get("athlete", {}).get("displayName", "")
        disp = top.get("displayValue", "")
        if athlete and disp:
            parts.append(f"{short_lbl}: {athlete} ({disp})")
    return "  |  ".join(parts)


def _extract_live_cmd_subtitle(comp: dict, away_abbr: str, home_abbr: str) -> str:
    """Build rich ⌘ modifier subtitle for Live games: Last Play + Drive + Win Prob."""
    situation = comp.get("situation", {})
    last_play = situation.get("lastPlay", {})
    play_text = last_play.get("text", "").strip()
    drive_desc = situation.get("drive", {}).get("description", "").strip()
    prob = last_play.get("probability", {})

    win_prob_str = ""
    home_wp = prob.get("homeWinPercentage")
    away_wp = prob.get("awayWinPercentage")
    if isinstance(home_wp, (int, float)) and isinstance(away_wp, (int, float)):
        if home_wp >= away_wp and home_wp > 0:
            win_prob_str = f"Win Prob: {home_abbr} {home_wp * 100:.0f}%"
        elif away_wp > 0:
            win_prob_str = f"Win Prob: {away_abbr} {away_wp * 100:.0f}%"

    segments = ["⌘ Box Score"]
    if win_prob_str:
        segments.append(win_prob_str)
    if drive_desc:
        segments.append(f"Drive: {drive_desc}")
    if play_text:
        segments.append(f"Last: {play_text}")
    return " · ".join(segments)


def _matches_filter(event: dict, query: str) -> bool:
    if not query:
        return True
    q = query.lower().strip()
    comp = event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    status = comp.get("status", {}).get("type", {})
    state = status.get("state", "pre")
    period = comp.get("status", {}).get("period", 0)

    home_c = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away_c = next((c for c in competitors if c.get("homeAway") == "away"), {})

    away_rank = get_curated_rank(away_c)
    home_rank = get_curated_rank(home_c)

    # Special filter keywords
    if q in ("top25", "top", "ranked", "rank", "ap", "cfp"):
        return away_rank <= 25 or home_rank <= 25

    if q == "live":
        return state == "in"

    if q in ("final", "post", "finished"):
        return state == "post"

    if q in ("upcoming", "pre", "scheduled"):
        return state == "pre"

    if q == "close":
        try:
            diff = abs(int(away_c.get("score", 0)) - int(home_c.get("score", 0)))
        except (ValueError, TypeError):
            diff = 99
        return state == "in" and period >= 3 and diff <= 8

    # Check team names, abbreviations, and conferences
    for c in (away_c, home_c):
        t = c.get("team", {})
        tid = str(t.get("id", ""))
        local_meta = TEAM_BY_ID.get(tid, {})
        haystack = " ".join([
            t.get("displayName", ""),
            t.get("shortDisplayName", ""),
            t.get("location", ""),
            t.get("name", ""),
            t.get("abbreviation", ""),
            local_meta.get("conference", ""),
            local_meta.get("conference_short", ""),
            " ".join(local_meta.get("conference_aliases", [])),
        ]).lower()
        if q in haystack:
            return True

    return False


def format_game_item(event: dict) -> tuple[dict, tuple]:
    """
    Format single event to Alfred item.
    Returns (item_dict, sort_tuple) where sort_tuple orders:
      (bucket_order, best_rank, start_date_str)
    """
    comp = event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])

    home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})

    home_team = home_comp.get("team", {})
    away_team = away_comp.get("team", {})

    home_id = str(home_team.get("id", ""))
    away_id = str(away_team.get("id", ""))

    home_abbr = home_team.get("abbreviation", "HOME")
    away_abbr = away_team.get("abbreviation", "AWAY")

    home_name = home_team.get("shortDisplayName") or home_team.get("location") or home_abbr
    away_name = away_team.get("shortDisplayName") or away_team.get("location") or away_abbr

    away_rank = get_curated_rank(away_comp)
    home_rank = get_curated_rank(home_comp)
    best_rank = min(away_rank, home_rank)

    away_rk_str = format_rank(away_rank)
    home_rk_str = format_rank(home_rank)

    home_score = str(home_comp.get("score", "0"))
    away_score = str(away_comp.get("score", "0"))

    status = comp.get("status", {}).get("type", {})
    state = status.get("state", "pre")  # 'in', 'pre', 'post'
    status_detail = status.get("shortDetail", status.get("detail", ""))
    start_date_str = event.get("date") or comp.get("startDate", "")

    broadcast = ""
    broadcasts = comp.get("broadcasts", [])
    if broadcasts:
        names = broadcasts[0].get("names", [])
        if names:
            broadcast = names[0]

    # Links
    eid = event.get("id", "")
    gamecast_url = f"https://www.espn.com/college-football/game/_/gameId/{eid}"
    boxscore_url = f"https://www.espn.com/college-football/boxscore/_/gameId/{eid}"
    pbp_url      = f"https://www.espn.com/college-football/playbyplay/_/gameId/{eid}"

    for l in event.get("links", []):
        rel = l.get("rel", [])
        if "boxscore" in rel:
            boxscore_url = l.get("href", boxscore_url)
        elif "pbp" in rel:
            pbp_url = l.get("href", pbp_url)
        elif "live" in rel or "summary" in rel:
            gamecast_url = l.get("href", gamecast_url)

    icon_path = matchup_icon_path(away_id, home_id)
    leaders_str = _extract_leaders_summary(comp)
    alt_sub = f"⌥ Play-by-Play · {leaders_str}" if leaders_str else "⌥ Open Play-by-Play"

    # 1. LIVE GAME
    if state == "in":
        situation = comp.get("situation", {})
        down_dist = situation.get("downDistanceText", "")
        possession_id = str(situation.get("possession", ""))
        possession_abbr = away_abbr if away_id == possession_id else (
            home_abbr if home_id == possession_id else ""
        )
        is_redzone = situation.get("isRedZone", False)
        away_to = situation.get("awayTimeouts")
        home_to = situation.get("homeTimeouts")

        sub_parts = []
        if possession_abbr and down_dist:
            sub_parts.append(f"🏈 {possession_abbr} {down_dist}")
        elif down_dist:
            sub_parts.append(f"🏈 {down_dist}")
        else:
            sub_parts.append(f"🔴 LIVE · {away_name} @ {home_name}")

        if is_redzone:
            sub_parts.append("🔴 RED ZONE")

        if away_to is not None and home_to is not None:
            sub_parts.append(f"· TO: {away_abbr} {away_to}, {home_abbr} {home_to}")

        if broadcast:
            sub_parts.append(f"· {broadcast}")

        subtitle = " ".join(sub_parts)
        title = f"{away_rk_str}{away_abbr} {away_score}   {home_rk_str}{home_abbr} {home_score}   —  {status_detail}"
        cmd_sub = _extract_live_cmd_subtitle(comp, away_abbr, home_abbr)

        return {
            "title": title,
            "subtitle": subtitle,
            "arg": gamecast_url,
            "icon": {"path": icon_path},
            "mods": {
                "cmd": {"subtitle": cmd_sub, "arg": boxscore_url},
                "alt": {"subtitle": alt_sub, "arg": pbp_url},
            }
        }, (0, best_rank, start_date_str)

    # 2. UPCOMING GAME
    if state == "pre":
        time_display = utc_to_local(start_date_str) if start_date_str else "TBD"
        away_record = away_comp.get("records", [{}])[0].get("summary", "") if away_comp.get("records") else ""
        home_record = home_comp.get("records", [{}])[0].get("summary", "") if home_comp.get("records") else ""
        matchup_names = f"{away_name} ({away_record}) @ {home_name} ({home_record})" if away_record and home_record else f"{away_name} @ {home_name}"

        venue = comp.get("venue", {}).get("fullName", "")
        sub_items = [s for s in [matchup_names, venue, broadcast] if s]
        subtitle = " · ".join(sub_items)

        title = f"{away_rk_str}{away_abbr}  @  {home_rk_str}{home_abbr}   —  {time_display}"

        return {
            "title": title,
            "subtitle": subtitle,
            "arg": gamecast_url,
            "icon": {"path": icon_path},
            "mods": {
                "cmd": {"subtitle": "⌘ Open Game Preview", "arg": gamecast_url},
                "alt": {"subtitle": alt_sub, "arg": pbp_url},
            }
        }, (1, best_rank, start_date_str)

    # 3. FINAL GAME
    away_record = away_comp.get("records", [{}])[0].get("summary", "") if away_comp.get("records") else ""
    home_record = home_comp.get("records", [{}])[0].get("summary", "") if home_comp.get("records") else ""
    rec_parts = []
    if away_record:
        rec_parts.append(f"{away_name} ({away_record})")
    else:
        rec_parts.append(away_name)
    if home_record:
        rec_parts.append(f"{home_name} ({home_record})")
    else:
        rec_parts.append(home_name)

    subtitle = " · ".join(rec_parts)
    if leaders_str:
        cmd_sub = f"⌘ Box Score · {leaders_str}"
    else:
        cmd_sub = "⌘ Open Box Score"

    title = f"{away_rk_str}{away_abbr} {away_score}   {home_rk_str}{home_abbr} {home_score}   —  {status_detail or 'Final'}"

    return {
        "title": title,
        "subtitle": subtitle,
        "arg": boxscore_url,
        "icon": {"path": icon_path},
        "mods": {
            "cmd": {"subtitle": cmd_sub, "arg": boxscore_url},
            "alt": {"subtitle": alt_sub, "arg": pbp_url},
        }
    }, (2, best_rank, start_date_str)


def scores_main(filter_query: str = ""):
    key = "cfb_fbs_scoreboard"
    data = cache_get(key, CACHE_TTL)
    if not data:
        stale = cache_get_stale(key)
        try:
            data = api_get(SCOREBOARD_URL)
            cache_set(key, data)
        except Exception as e:
            if stale:
                data = stale
            else:
                alfred_error("Could not fetch NCAA FBS scores", str(e))
                return

    events = data.get("events", [])
    if filter_query:
        events = [ev for ev in events if _matches_filter(ev, filter_query)]

    if not events:
        msg = f"No FBS games matching '{filter_query}'" if filter_query else "No NCAA FBS games scheduled for this week 🏈"
        sub = "Try: top25, live, close, sec, big10, b12, acc, or a school name" if filter_query else "Check back soon for upcoming matchups"
        alfred_output([{
            "title": msg,
            "subtitle": sub,
            "valid": False,
            "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")}
        }])
        return

    formatted_items = []
    has_live = False

    for ev in events:
        try:
            item, sort_tuple = format_game_item(ev)
            if sort_tuple[0] == 0:
                has_live = True
            formatted_items.append((sort_tuple, item))
        except Exception:
            continue

    # Sort by (state_bucket, best_curated_rank, start_date)
    formatted_items.sort(key=lambda x: x[0])
    items = [item for _, item in formatted_items]

    alfred_output(items, rerun=RERUN_LIVE if has_live else None)


if __name__ == "__main__":
    main()
