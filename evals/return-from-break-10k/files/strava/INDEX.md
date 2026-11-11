# Saved Strava connector responses

There is no live Strava connection in this test. Each file below is the JSON one connector call returned
for this athlete. Values are raw SI units (metres, seconds, m/s), as the connector returns them by default.
Today is Tuesday 2 June 2026.

| File | Connector call it stands for |
|---|---|
| `get_athlete_profile.json` | `get_athlete_profile` |
| `get_athlete_zones.json` | `get_athlete_zones` |
| `search_activities.runs_last_12_weeks.json` | `search_activities`, sport_types ["Run","TrailRun","VirtualRun"], start_date_min 2026-03-09, include_tags true, first 100 |
| `search_activities.longest_runs_12_months.json` | `search_activities`, sport_types ["Run","TrailRun","VirtualRun"], start_date_min 2025-06-02, sort_field DISTANCE, first 5 |
| `search_activities.first_run.json` | `search_activities`, sport_types ["Run","TrailRun","VirtualRun"], sort_field START_DATE, sort_descending false, first 1 |
| `search_activities.races_18_months.json` | `search_activities`, sport_types ["Run","TrailRun","VirtualRun"], tags ["RACE"], start_date_min 2024-12-02, include_tags true, first 20 |
| `get_athlete_best_efforts.json` | `get_athlete_best_efforts`, sports ["Run"], years [2026, 2025], best_effort_types ["Fastest5k","Fastest10k","FastestHalfMarathon","FastestMarathon"] |
| `search_activities.other_sports_4_weeks.json` | `search_activities`, sport_types ["Ride","VirtualRide","GravelRide","MountainBikeRide","Swim","Hike","WeightTraining","Workout","Crossfit","HighIntensityIntervalTraining","Rowing","NordicSki","Elliptical","Yoga","Pilates"], start_date_min 2026-05-05, moving_time_min 1200, is_commute false |
| `get_activity_performance.9200000140.json` | `get_activity_performance`, activity_id 9200000140 ("Footing", 2026-04-14) |
| `get_activity_performance.9200000175.json` | `get_activity_performance`, activity_id 9200000175 ("parkrun", 2026-03-28) |
| `get_activity_performance.9200000182.json` | `get_activity_performance`, activity_id 9200000182 ("Reprise en douceur", 2026-05-24) |
| `get_activity_performance.9200000189.json` | `get_activity_performance`, activity_id 9200000189 ("Footing", 2026-05-28) |
| `get_activity_performance.9200000196.json` | `get_activity_performance`, activity_id 9200000196 ("Footing du dimanche", 2026-05-31) |

Nothing else is available offline (no streams, no gear, no other activities' details).
