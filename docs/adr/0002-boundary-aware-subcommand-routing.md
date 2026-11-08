# Use Boundary-Aware Subcommand Routing with Dual Triggers

Status: accepted

We will configure two Script Filter triggers (`cfb` and `ncaaf`) in `info.plist` with `withspace: false`, both invoking `python3 cfb.py "$1"`, and route to subcommands (`s`, `r`, `t`, `c`) only when the subcommand character is the entire query or is immediately followed by whitespace.

## Context & Trade-offs

In the existing `mlb` and `nfl` workflows, `withspace: false` lets a single Script Filter handle `nfl`, `nfls`, `nflp`, and `nflt` by checking `query.startswith("s")` or `query.startswith("t")`. However, in college football where 60+ FBS games occur each week, users need to filter the live scoreboard by typing a team, conference, or bucket after a space (e.g., `cfb texas`, `cfb sec`, `cfb top25`). Naive `.startswith()` routing treats `cfb texas` (`query = "texas"`) as `cfbt exas` and `cfb sec` (`query = "sec"`) as `cfbs ec`.

By inspecting raw `sys.argv[1]` before stripping leading spaces:
- Leading-space queries (`raw_query.startswith(" ")`, e.g., `cfb texas`, `cfb sec`, `cfb top25`) always route to the **Scoreboard (`cfb.py`)** as a filter.
- Non-leading-space queries starting with `s`, `r`, `t`, or `c` where the remainder is empty or starts with a space (`cfbs`, `cfbs sec`, `cfbr`, `cfbr ap`, `cfbt texas`, `cfbc texas`) route to the respective subcommand module.
