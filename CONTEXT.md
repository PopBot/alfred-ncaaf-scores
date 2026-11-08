# NCAA FBS Football Alfred Workflow

An Alfred 5 workflow for tracking NCAA Division I FBS college football live scores, conference standings, national poll rankings, team statistics, and season schedules via ESPN's public API.

## Language

**FBS (Football Bowl Subdivision)**:
The top level of NCAA Division I college football (`groups=80` in ESPN's API), consisting of the 10 FBS conferences and FBS Independents. All workflow queries are strictly scoped to FBS; FCS (`groups=81`) and lower divisions are excluded.
_Avoid_: D1-A, FCS, Division I-AA

**Poll (National Ranking)**:
An official top-25 ranking of FBS teams published weekly during the season, specifically the College Football Playoff (CFP) Rankings (`cfp`), the AP Top 25 (`ap`), or the AFCA Coaches Poll (`usa`).
_Avoid_: Power ranking, leaderboard, tier list

**Curated Rank**:
A team's official top-25 rank (`1`–`25`) attached to a matchup or schedule entry; ESPN represents unranked teams with the sentinel value `99`, which is hidden in display output.
_Avoid_: Seed, raw rank

**Matchup**:
A single game between an away team and a home team in one of three states: Live (`in`), Upcoming (`pre`), or Final (`post`).
_Avoid_: Event, competition, fixture

**Boundary-Aware Subcommand**:
A single-letter command suffix (`s` for Standings, `r` for Rankings, `t` for Team + Schedule, `c` as direct alias for Team + Schedule) attached directly to the base trigger keyword (`cfb` or `ncaaf`) that only activates when the suffix is exact or immediately followed by a space, preventing collisions with scoreboard text filters (e.g., `cfb texas`, `cfb sec`, `cfb top25`).
_Avoid_: Prefix route, raw prefix

**Matchup Icon**:
A dynamically composited 64×64 PNG showing the away team logo on the left and the home team logo on the right, keyed by numeric ESPN Team IDs (`matchup_{away_id}_{home_id}.png`) to prevent college abbreviation collisions.
_Avoid_: Dual logo, game thumbnail

**Unified Team View**:
The response layout for a single matched FBS team (`cfbt {team}` or `cfbc {team}`), where the first row presents the team's season record and `⌘` Offense / `⌥` Defense statistics, and the subsequent rows display the team's full 12-game season schedule inline.
_Avoid_: Separate schedule tab, external schedule link
