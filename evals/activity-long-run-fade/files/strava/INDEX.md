# Saved Strava connector responses

There is no live Strava connection in this test. Each file below is the JSON one connector call returned
for this athlete. Values are raw SI units (metres, seconds, m/s), as the connector returns them by default.
Today is Tuesday 2 June 2026.

| File | Connector call it stands for |
|---|---|
| `get_athlete_profile.json` | `get_athlete_profile` |
| `get_athlete_zones.json` | `get_athlete_zones` |
| `search_activities.runs_last_6_weeks.json` | `search_activities`, sport_types ["Run","TrailRun","VirtualRun"], start_date_min 2026-04-21, include_tags true, first 60 |
| `search_activities.races_18_months.json` | `search_activities`, sport_types ["Run","TrailRun","VirtualRun"], tags ["RACE"], start_date_min 2024-12-02, include_tags true, first 20 |
| `get_athlete_best_efforts.json` | `get_athlete_best_efforts`, sports ["Run"], years [2026, 2025], best_effort_types ["Fastest5k","Fastest10k","FastestHalfMarathon","FastestMarathon"] |
| `get_activity_performance.9400000112.json` | `get_activity_performance`, activity_id 9400000112 ("Sunday long run", 2026-05-17) |
| `get_activity_performance.9400000140.json` | `get_activity_performance`, activity_id 9400000140 ("Sunday long run", 2026-05-24) |
| `get_activity_performance.9400000147.json` | `get_activity_performance`, activity_id 9400000147 ("Morning run", 2026-05-26) |
| `get_activity_performance.9400000168.json` | `get_activity_performance`, activity_id 9400000168 ("Half marathon distance!", 2026-05-31) |
| `get_activity_streams.9400000168.json` | `get_activity_streams`, activity_id 9400000168 ("Half marathon distance!", 2026-05-31), streams ["time","distance","heart_rate","altitude"], resolution 200 |

Nothing else is available offline: streams exist for that one activity only, at that resolution, and there are no other activities' details and no gear.
