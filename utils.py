#!/usr/bin/env python3
"""
utils.py — Shared utilities for the NCAA FBS Football (cfb / ncaaf) Alfred workflow.
Bundled lib/ is loaded first so requests always works regardless of
which Python version Alfred uses on the Mac.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

# ── Bundled dependencies ──────────────────────────────────────────────────────
WORKFLOW_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(WORKFLOW_DIR, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import requests
from image_utils import make_matchup_icon

# ── Paths ─────────────────────────────────────────────────────────────────────
DEFAULT_ALFRED_CACHE = os.path.expanduser(
    "~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.popbot.alfred-ncaaf-scores"
)
CACHE_DIR  = os.environ.get("alfred_workflow_cache") or DEFAULT_ALFRED_CACHE
LOGO_DIR   = os.path.join(WORKFLOW_DIR, "cfb_logos")
TEAMS_FILE = os.path.join(WORKFLOW_DIR, "data", "teams.json")

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Teams ─────────────────────────────────────────────────────────────────────
with open(TEAMS_FILE) as f:
    TEAMS: list[dict] = json.load(f)

TEAM_BY_ID: dict[str, dict] = {str(t["id"]): t for t in TEAMS}

# ── HTTP Session ──────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.clear()
_session.headers.update({
    "User-Agent": "curl/8.7.1",
    "Accept": "*/*",
})


def api_get(url: str, params: dict | None = None, timeout: int = 6) -> dict:
    r = _session.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def team_logo_path(team_id: str | int) -> str:
    """
    Return path to 64x64 PNG logo keyed by numeric ESPN team_id.
    If an opponent (e.g. non-bundled opponent on a schedule) is not in cfb_logos/,
    checks CACHE_DIR or falls back to icon.png.
    """
    tid = str(team_id).strip()
    if not tid:
        return os.path.join(WORKFLOW_DIR, "icon.png")

    bundled = os.path.join(LOGO_DIR, f"{tid}.png")
    if os.path.exists(bundled):
        return bundled

    cached_logo = os.path.join(CACHE_DIR, f"logo_{tid}.png")
    if os.path.exists(cached_logo):
        return cached_logo

    return os.path.join(WORKFLOW_DIR, "icon.png")


def matchup_icon_path(away_id: str | int, home_id: str | int) -> str:
    """
    Generate or retrieve a cached 64x64 dual-logo matchup icon keyed by numeric
    away_id and home_id (preventing college abbreviation collisions).
    """
    aid = str(away_id).strip()
    hid = str(home_id).strip()
    name = f"matchup_{aid}_{hid}.png"
    out_path = os.path.join(CACHE_DIR, name)
    if os.path.exists(out_path):
        return out_path

    away_logo = team_logo_path(aid)
    home_logo = team_logo_path(hid)
    if make_matchup_icon(away_logo, home_logo, out_path):
        return out_path
    return home_logo


def format_rank(rank_val: int | str | None) -> str:
    """Return '#N ' if rank is between 1 and 25 inclusive, else empty string."""
    try:
        r = int(rank_val)
        if 1 <= r <= 25:
            return f"#{r} "
    except (ValueError, TypeError):
        pass
    return ""


def get_curated_rank(competitor: dict) -> int:
    """Extract numeric curatedRank.current (1..25), or 99 if unranked."""
    try:
        r = int(competitor.get("curatedRank", {}).get("current", 99))
        return r if 1 <= r <= 25 else 99
    except (ValueError, TypeError):
        return 99


def parse_standings_entry_stats(stats_list: list[dict]) -> dict[str, str]:
    """
    Safely parse an ESPN college football standings entry's stats array without
    letting split stats (homerecord_*, awayrecord_*, vsdivision_*, vsconf_*,
    vsaprankedteams_*, vsusarankedteams_*) overwrite overall season stats.
    """
    base: dict[str, str] = {}
    by_type: dict[str, str] = {}

    for s in stats_list:
        stype = s.get("type", "")
        sname = s.get("name", "")
        sval  = s.get("displayValue")
        if sval is None:
            continue
        if stype:
            by_type[stype] = str(sval)
        # Only store in base if type does NOT contain '_' (i.e. not a split record)
        if "_" not in stype and sname:
            base[sname] = str(sval)

    overall = by_type.get("total") or base.get("overall", "0-0")
    conf_rec = by_type.get("vsconf") or base.get("vs. Conf.", "0-0")
    vs_ap = by_type.get("vsaprankedteams") or base.get("vs AP Top 25", "0-0")
    home_rec = by_type.get("homerecord") or base.get("Home", "—")
    away_rec = by_type.get("awayrecord") or base.get("Away", "—")
    diff = by_type.get("pointdifferential") or base.get("pointDifferential", "0")
    if diff and not diff.startswith("+") and not diff.startswith("-") and diff != "0":
        diff = f"+{diff}"
    pf = by_type.get("pointsfor") or base.get("pointsFor", "0")
    pa = by_type.get("pointsagainst") or base.get("pointsAgainst", "0")
    streak = by_type.get("streak") or base.get("streak", "—")
    seed = by_type.get("playoffseed") or base.get("playoffSeed", "—")

    return {
        "overall": overall,
        "conf_rec": conf_rec,
        "vs_ap": vs_ap,
        "home": home_rec,
        "away": away_rec,
        "diff": diff,
        "pf": pf,
        "pa": pa,
        "streak": streak,
        "seed": seed,
    }


# ── File Cache ────────────────────────────────────────────────────────────────
def cache_get(key: str, ttl: int):
    """Return cached data only if younger than ttl seconds, else None."""
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def cache_get_stale(key: str):
    """Return cached data regardless of age (stale-while-revalidate). None if missing."""
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def cache_set(key: str, data) -> None:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# ── Timezone ──────────────────────────────────────────────────────────────────
def utc_to_local_datetime(utc_str: str) -> datetime:
    """Convert '2026-11-07T20:30Z' to local datetime."""
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    return dt.astimezone()


def utc_to_local(utc_str: str, include_date: bool = False) -> str:
    """Format local time like 'Sat 12:30 PM' or 'Today 4:00 PM' (or 'Sat Nov 14, 12:30 PM')."""
    try:
        local = utc_to_local_datetime(utc_str)
        now = datetime.now().astimezone()
        if local.date() == now.date():
            day_str = "Today"
        elif include_date:
            day_str = local.strftime("%a %b %-d,")
        else:
            day_str = local.strftime("%a")
        return f"{day_str} {local.strftime('%-I:%M %p')}"
    except Exception:
        return "TBD"


def utc_to_short_date(utc_str: str) -> str:
    """Format '2026-09-05T16:00Z' as 'Sep 5' in local timezone."""
    try:
        local = utc_to_local_datetime(utc_str)
        return local.strftime("%b %-d")
    except Exception:
        return ""


# ── Alfred Output ─────────────────────────────────────────────────────────────
def alfred_error(message: str, detail: str = "") -> None:
    items = [{
        "title": f"⚠️ {message}",
        "subtitle": detail,
        "valid": False,
        "icon": {"path": os.path.join(WORKFLOW_DIR, "icon.png")}
    }]
    print(json.dumps({"items": items}))
    sys.exit(0)


def alfred_output(items: list, rerun: float | None = None) -> None:
    out: dict = {"items": items}
    if rerun:
        out["rerun"] = rerun
    print(json.dumps(out))
