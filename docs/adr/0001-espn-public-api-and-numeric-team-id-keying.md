# Use ESPN Public API and Numeric Team ID Keying

Status: accepted

We will use ESPN's public JSON API (`site.api.espn.com`) scoped to FBS (`groups=80`) as the sole data source, and key all local team metadata, 64×64 PNG logos, and cached matchup icons by numeric ESPN `team_id` (`{team_id}.png`) rather than team abbreviation.

## Considered Options

- **ESPN Public API (`site.api.espn.com`)**: Zero authentication, Akamai CDN speed (~100–250ms), single-call live situation data (`downDistanceText`, `possession`, `isRedZone`, `homeTimeouts`, `awayTimeouts`, `lastPlay.text`, `probability`), all 3 FBS polls (`CFP`, `AP`, `AFCA Coaches`), full conference standings, and single-call 12-game team schedules.
- **NCAA.com Wrapper (`ncaa-api.henrygd.me`)**: Free and keyless, but scoreboard responses omit live down & distance, yard line, possession, red zone, and timeouts; lacks a single-endpoint per-team 12-game schedule and team offensive/defensive season stats; rate-limited to 5 req/sec via a community proxy.
- **CollegeFootballData (`api.collegefootballdata.com`)**: Rich historical and advanced metrics, but requires a personal Bearer API key with monthly quota limits, breaking the zero-config distribution model of our Alfred workflows.
- **Fox Sports / CBS Sports / Yahoo / TheSportsDB**: Either return 403/404, fail DNS resolution, or return empty/delayed college football scoreboards without API tokens.

## Consequences

- Unlike the 30-team MLB and 32-team NFL workflows (which name logos `{ABBR}.png`), 134 FBS programs have overlapping abbreviations (`USC` for Southern California vs. South Carolina, `MIA` for Miami FL vs. Miami OH, `OSU` for Ohio State / Oklahoma State / Oregon State, `UT` for Texas / Tennessee / Toledo). Storing logos as `cfb_logos/{team_id}.png` and matchup icons as `matchup_{away_id}_{home_id}.png` eliminates all filename collisions while matching ESPN's CDN URL structure (`https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png`).
