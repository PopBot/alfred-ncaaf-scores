# 🎯 NCAA FBS Football (`cfb` / `ncaaf`) Alfred Workflow — Specification & Architecture Plan

## 1. Overview
Build a standalone, zero-dependency Alfred 5 workflow for **NCAA Division I FBS College Football** (`groups=80` in ESPN's API). It evolves the architecture of [alfred-mlb-scores](file:///Users/jarodwong/Documents/Alfred%20Workflows/mlb/alfred-mlb-scores) and [alfred-nfl-scores](file:///Users/jarodwong/Documents/Alfred%20Workflows/nfl/alfred-nfl-scores), tailored to the unique structure of FBS college football (134 teams, 10 conferences + Independents, Top 25 Polls, 60+ games per week, and 12-game team schedules).

### Key Architectural Highlights
- **Strictly FBS (`groups=80`)**: All scores, standings, rankings, and team lookups are scoped to the 134 FBS programs (no FCS clutter).
- **Dual Trigger Keywords (`cfb` & `ncaaf`)**: Both keywords are wired in `info.plist` (`withspace: false`) to the same entry-point router (`cfb.py`).
- **Boundary-Aware Subcommand Routing**: Distinguishes subcommands (`cfbs`, `cfbr`, `cfbt`, `cfbc`) from space-separated scoreboard filters (`cfb texas`, `cfb sec`, `cfb top25`, `cfb close`). See [ADR-0002](file:///Users/jarodwong/Documents/Alfred%20Workflows/ncaaf/docs/adr/0002-boundary-aware-subcommand-routing.md).
- **Numeric Team ID Keying**: Unlike MLB/NFL, college teams share abbreviations (`USC`, `MIA`, `OSU`, `UT`). All 134 logos (`cfb_logos/{team_id}.png`) and composite matchup icons (`matchup_{away_id}_{home_id}.png`) are keyed by ESPN's numeric `team_id`. See [ADR-0001](file:///Users/jarodwong/Documents/Alfred%20Workflows/ncaaf/docs/adr/0001-espn-public-api-and-numeric-team-id-keying.md).
- **Rich Live Game Modifiers**: Live games surface Down & Distance, Possession, Red Zone, and TV Network by default, plus **Last Play / Drive / Live Win Probability** on `⌘` and **Passing / Rushing / Receiving Game Leaders** on `⌥`—all from a single scoreboard API call.
- **Unified Team + 12-Game Schedule View**: When `cfbt {team}` (or `cfbc {team}`) matches a single school, Row 1 displays the team's record and `⌘` Offense / `⌥` Defense season stats, while Rows 2–13 display the school's full 12+ game season schedule inline.
- **No Player Stats Module**: Intentionally omitted per requirements to keep the workflow fast and focused on FBS teams, games, polls, and conferences.

---

## 2. Alfred Keystroke Commands & UX Flow

Two Script Filter objects in `info.plist` (`keyword: cfb` and `keyword: ncaaf`, both `withspace: false`) pass `"$1"` (unstripped) to `python3 cfb.py "$1"`:

| Command (`cfb` or `ncaaf`) | Raw `$1` | Routed Module & Behavior |
| :--- | :--- | :--- |
| `cfb` | `""` | **Scoreboard (`cfb.py`)**: All FBS games this week (`Live` → `Upcoming` → `Final`), with Top 25 matchups sorted first inside each bucket. |
| `cfb {filter}` | `" {filter}"` (starts with space) | **Filtered Scoreboard (`cfb.py`)**: Filters this week's FBS games by team (`cfb texas`), conference (`cfb sec`, `cfb b10`), `cfb top25` (ranked matchups), `cfb live`, or `cfb close` (4th Qtr/OT within 8 pts). |
| `cfbs` / `cfbs {conf}` | `"s"` or `"s {conf}"` | **Standings (`cfb_standings.py`)**: Conference standings ordered Power 4 first (`SEC`, `Big Ten`, `Big 12`, `ACC`), then `Pac-12`, Group of 5 (`American`, `Mountain West`, `Sun Belt East/West`, `MAC`, `C-USA`), and `Independents`. Optional `{conf}` filters to a single conference. |
| `cfbr` / `cfbr {poll}` | `"r"` or `"r {poll}"` | **Rankings (`cfb_rankings.py`)**: Smart default shows **CFP Rankings** when available (Nov–Jan) or falls back to **AP Top 25**. Supports `cfbr ap`, `cfbr cfp`, and `cfbr coaches`. |
| `cfbt {query}` / `cfbc {query}` | `"t {query}"` or `"c {query}"` | **Unified Team & Schedule (`cfb_team.py`)**: Multi-match shows one summary row per team (`⌘` Offense, `⌥` Defense). Single-team match shows Row 1 as Team Summary + Rows 2–13 as the team's full 12-game season schedule inline. |

---

## 3. Directory & File Structure

```text
ncaaf/
├── CONTEXT.md                  ← Domain model & ubiquitous language glossary
├── AGY_NCAAF_ALFRED_SPEC.md    ← This specification and architecture plan
├── docs/
│   └── adr/
│       ├── 0001-espn-public-api-and-numeric-team-id-keying.md
│       └── 0002-boundary-aware-subcommand-routing.md
└── alfred-ncaaf-scores/        ← Workflow source & packaging root (when implemented)
    ├── cfb.py                  ← Router + FBS Scoreboard (Live / Upcoming / Final + Filters)
    ├── cfb_standings.py        ← FBS Conference Standings (Power 4 prioritized + Sub-divisions)
    ├── cfb_rankings.py         ← Top 25 Polls (CFP Committee, AP Top 25, AFCA Coaches Poll)
    ├── cfb_team.py             ← Unified Team Stats (⌘ Off / ⌥ Def) + Inline 12-Game Schedule
    ├── utils.py                ← Cache, HTTP session, timezone helpers, numeric team_id lookups
    ├── image_utils.py          ← Pure-Python PNG decoder, resizer, and dual-logo compositor
    ├── download_logos.py       ← One-time build script to fetch 134 FBS logos ({team_id}.png)
    ├── build.py                ← Packages `NCAAF Scores.alfredworkflow`
    ├── info.plist              ← Alfred 5 workflow XML (dual `cfb` + `ncaaf` Script Filters)
    ├── icon.png                ← College football workflow icon
    ├── data/
    │   └── teams.json          ← Metadata for all 134 FBS teams (id, name, location, nickname, abbr, conference, conference_aliases)
    ├── cfb_logos/              ← 134 pre-downloaded 64×64 PNG logos named `{team_id}.png`
    └── lib/                    ← Vendored Python HTTP dependencies (`requests`, `urllib3`, `certifi`, `idna`, `charset_normalizer`)
```

---

## 4. ESPN API Endpoints & Data Nuances

### 4.1 FBS Scoreboard (`cfb.py`)
```http
GET https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=300
```
- **Why `groups=80&limit=300` is mandatory**: Omitting `groups=80` only returns ~16 featured games. Passing `groups=80&limit=300` returns all ~63–70 FBS matchups for the current week in one request (~120ms).
- **Curated Ranks**: Each competitor has `curatedRank.current` (`1`–`25`, or `99` if unranked). Display `#Rank` prefix whenever `1 <= current <= 25` (e.g., `#3 TEX 24  #7 UGA 21`).
- **Sorting**:
  1. State bucket: `Live ("in")` → `Upcoming ("pre")` → `Final ("post")`.
  2. Within each bucket: Sort by `min(away_rank, home_rank)` ascending (so Top 25 matchups float to the top), then chronologically by kickoff / quarter clock.
- **Modifier Subtitles (Zero Extra HTTP Calls)**:
  - **Default Live Subtitle**: `🏈 {POSS_ABBR} {downDistanceText} 🔴 RED ZONE · {broadcast} · TO: {away_abbr} {away_to}, {home_abbr} {home_to}`
  - **`⌘` (Cmd) Subtitle (Live)**: `⌘ Box Score · Last: {lastPlay.text} · Drive: {drive.description} · Win Prob: {win_prob_str}`
  - **`⌥` (Alt) Subtitle (Live & Final)**: `⌥ Play-by-Play · Leaders: {Pass Leader} | {Rush Leader} | {Rec Leader}` (parsed from `competitions[0].leaders`).

### 4.2 National Polls / Rankings (`cfb_rankings.py`)
```http
GET https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings
```
- Inspects `rankings[]` for FBS polls by `type`:
  - `"cfp"` → **Playoff Committee Rankings** (default when present in response)
  - `"ap"` → **AP Top 25** (default fallback in Sep/Oct, or via `cfbr ap`)
  - `"usa"` → **AFCA Coaches Poll** (via `cfbr coaches` or `cfbr usa`)
- **Row Format**:
  - *Title*: `#{current} {team.location} {team.name}  ({recordSummary})`
  - *Subtitle*: `{conference.shortName} · Trend: {trend} · Points: {points} ({firstPlaceVotes} 1st-place votes)`
  - *Icon*: `cfb_logos/{team.id}.png`

### 4.3 FBS Conference Standings (`cfb_standings.py`)
```http
GET https://site.api.espn.com/apis/v2/sports/football/college-football/standings?group=80
```
- **Critical Bug Fix over NFL Workflow**: In ESPN's CFB standings, `entry["stats"]` repeats `name: "wins"`, `name: "pointDifferential"`, `name: "pointsFor"`, `name: "pointsAgainst"`, and `name: "streak"` 7 times (for `total`, `homerecord_*`, `awayrecord_*`, `vsdivision_*`, `vsconf_*`, `vsaprankedteams_*`, `vsusarankedteams_*`).
  - **Rule**: Map stats by `(s.get("type"), s.get("name"))` or only read base stats where `"_" not in s.get("type", "")`, plus explicitly extract `type == "vsconf"` for conference record (`5-1`) and `type == "vsaprankedteams"` for record vs. Top 25 (`2-0`).
- **Flat vs. Divided Conferences**:
  - 10 of 11 FBS groups store teams directly in `conf["standings"]["entries"]`.
  - **Sun Belt Conference (`id: "37"`)** stores teams inside `conf["children"]` (`Sun Belt - East` and `Sun Belt - West`). The parser must check `if conf.get("children"):` and render sub-division headers accordingly.
- **Conference Priority Order & Filter Aliases**:
  1. **Southeastern Conference** (`sec`)
  2. **Big Ten Conference** (`b10`, `big10`, `big ten`)
  3. **Big 12 Conference** (`b12`, `big12`, `big 12`)
  4. **Atlantic Coast Conference** (`acc`)
  5. **Pac-12 Conference** (`pac12`, `pac`)
  6. **American Conference** (`aac`, `american`)
  7. **Mountain West Conference** (`mw`, `mwc`, `mountain west`)
  8. **Sun Belt Conference** (`sbc`, `sun belt`) — East & West
  9. **Mid-American Conference** (`mac`)
  10. **Conference USA** (`cusa`, `c-usa`)
  11. **FBS Independents** (`ind`, `independent`)

### 4.4 Unified Team Stats & 12-Game Schedule (`cfb_team.py`)
```http
GET https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/statistics
GET https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/schedule
```
- **Multi-Team Match (`len(matched_teams) > 1`)**:
  - Displays up to 15 matching teams sorted by Conference / Win %.
  - To prevent the sequential HTTP bottleneck found in `nfl_team.py`, fetch `/teams/{id}/statistics` concurrently using `ThreadPoolExecutor(max_workers=6)` only for the top 6 matches (or lazy-load when `len(matched_teams) <= 6`).
- **Single-Team Match (`len(matched_teams) == 1`, e.g., `cfbt texas` or `cfbc texas`)**:
  - **Row 1 (Team Overview)**:
    - *Title*: `{#Rank} {Team Name} — {Overall Record} ({Conf Record} {Conf Abbr})`
    - *Subtitle*: `Streak: {streak} · PF: {pf} · PA: {pa} · Diff: {diff} · vs Top 25: {vs_ap}`
    - *`⌘` (Cmd)*: `⌘ Offense: {PPG} PPG · Pass: {Pass YDS} YDS ({Pass TD} TD) · Rush: {Rush YDS} YDS ({Rush TD} TD)`
    - *`⌥` (Alt)*: `⌥ Defense: {Sacks} Sacks · {INTs} INTs · {Forced Fum} FF · {Tackles} Tackles`
  - **Rows 2–14 (Inline Season Schedule from `/teams/{id}/schedule`)**:
    - Normalizes `competitor["score"]` (which is a `dict` `{"displayValue": "48"}` on `/schedule` vs. a `str` on `/scoreboard`) and `broadcasts[0]["media"]["shortName"]`.
    - *Completed Game*: `Wk 1 · W 48-10 vs East Carolina` (Subtitle: `Sep 5 · Final · Home`)
    - *Live Game*: `Wk 10 · 🔴 LIVE: #11 ALA 24 @ #15 LSU 21 — 4:12 3rd`
    - *Upcoming Game*: `Wk 11 · @ Vanderbilt — Sat Nov 14, 1:45 PM` (Subtitle: `FirstBank Stadium · SEC Network`)
    - *Icon*: Composite matchup icon `matchup_{away_id}_{home_id}.png` (or opponent logo if FCS/non-FBS opponent logo is fetched on-demand into cache).

---

## 5. Caching Strategy (`utils.py`)
- Uses Alfred's `$alfred_workflow_cache` (`~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.popbot.alfred-ncaaf-scores`).
- Stale-while-revalidate fallback on network errors.
- **TTLs**:
  - Scoreboard (`cfb`): `30` seconds (`"rerun": 5.0` when any displayed game is live)
  - Standings (`cfbs`): `300` seconds (5 minutes)
  - Rankings (`cfbr`): `600` seconds (10 minutes)
  - Team Stats & Schedule (`cfbt` / `cfbc`): `300` seconds (5 minutes)
