# 🏈 NCAAF Scores (FBS) — Alfred 5 Workflow

Track **NCAA Division I FBS College Football** live scores, national Top 25 polls (CFP, AP, Coaches), conference standings, team offensive/defensive stats, and full 12-game season schedules directly inside Alfred 5.

## Features
- **Dual Keywords (`cfb` & `ncaaf`)**: Use whichever trigger feels faster.
- **Strictly FBS (`groups=80`)**: All 138 FBS teams across the 10 FBS conferences + Independents, with 64×64 PNG logos keyed by numeric ESPN Team ID (`cfb_logos/{team_id}.png`) to prevent abbreviation collisions (`USC`, `MIA`, `OSU`, `UT`).
- **Rich Live Game Context**:
  - **Default**: Score, AP/CFP `#Rank`, Quarter/Clock, Possession, Down & Distance, Red Zone alert, Timeouts remaining, and TV Broadcast.
  - **`⌘` (Cmd)**: Previews **Last Play text + Drive Summary + Live Win Probability %** inline (opens Box Score on Enter).
  - **`⌥` (Alt)**: Previews **Passing / Rushing / Receiving Game Leaders** inline (opens Play-by-Play on Enter).
- **National Polls (`cfbr` / `ncaafr`)**: Smart-defaults to the **College Football Playoff (CFP) Rankings** when available (Nov–Jan) and falls back to the **AP Top 25**. Switch polls anytime with `cfbr cfp`, `cfbr ap`, or `cfbr coaches`.
- **Conference Standings (`cfbs` / `ncaafs`)**: Ordered Power 4 first (`SEC`, `Big Ten`, `Big 12`, `ACC`), then `Pac-12`, Group of 5 (including `Sun Belt East/West` sub-divisions), and `FBS Independents`. Filter by conference with `cfbs sec`, `cfbs b10`, `cfbs b12`, `cfbs acc`, `cfbs mw`, `cfbs sbc`, etc.
- **Unified Team & 12-Game Schedule View (`cfbt {team}` / `cfbc {team}`)**: When matching a single school (e.g., `cfbt texas`), Row 1 shows the Team Summary (`⌘` Offense / `⌥` Defense season stats) and Rows 2–13 display the school's entire 12-game season schedule inline.
- **Zero Dependencies**: Bundled `requests` in `lib/` and pure-Python PNG compositing in `image_utils.py`.

## Usage

| Command | Description |
| :--- | :--- |
| `cfb` or `ncaaf` | Current week's FBS scores (Live → Upcoming → Final, Top 25 prioritized) |
| `cfb top25` | Filter scoreboard to Top 25 ranked matchups |
| `cfb sec` / `cfb b10` | Filter scoreboard to a specific conference |
| `cfb texas` | Filter scoreboard to a specific school |
| `cfb close` | Filter scoreboard to close live games (3rd/4th Qtr or OT within 8 pts) |
| `cfbr` / `cfbr ap` / `cfbr cfp` / `cfbr coaches` | View CFP Rankings, AP Top 25, or AFCA Coaches Poll |
| `cfbs` / `cfbs sec` / `cfbs b10` | View all FBS conference standings or filter to a single conference |
| `cfbt texas` or `cfbc texas` | View Texas's record (`⌘` Offense, `⌥` Defense) + full 12-game season schedule |

## Building
```bash
python3 build.py
```
Creates `NCAAF Scores.alfredworkflow`. Double-click to install in Alfred 5.
