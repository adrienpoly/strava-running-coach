#!/usr/bin/env python3
"""Generate the synthetic Strava fixtures used by the eval cases.

The runners are invented. The JSON mirrors the shape of the Strava connector's
responses (raw SI units), including the mess real logs contain: duplicate
uploads, split outings, paused runs, GPS-long race distances, stale zones.

    python3 tools/make_fixtures.py          # rewrites evals/*/files/strava/

Everything is deterministic: "today" for all cases is Tuesday 2 June 2026.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "evals"
TODAY = date(2026, 6, 2)
UNITS = {"avg_speed": "meters/second", "distance": "meters", "elapsed_time": "seconds",
         "elevation_gain": "meters", "max_speed": "meters/second", "moving_time": "seconds",
         "relative_effort": "unitless", "total_calories": "kilocalories", "weather.feels_like": "celsius",
         "weather.humidity": "percent", "weather.temperature": "celsius", "weather.wind_speed": "meters/second"}
RE_PER_MIN = {"easy": 0.9, "long": 1.15, "workout": 1.7, "race": 3.2, "other": 0.5}


class Log:
    """One runner's activity log, plus the per-activity detail we choose to expose."""

    def __init__(self, first_id, city):
        self.next_id, self.city, self.acts, self.perf = first_id, city, [], {}

    def add(self, day, clock, km, pace, name, kind="easy", *, sport="Run", desc=None, tags=None, elev=None,
            pause=0, trainer=False, manual=False, hr=None, laps=None, temp=14, moving=None, bests=None):
        """pace is seconds per km; hr is (average, max); laps is a list of (metres, seconds, avg_hr)."""
        self.next_id += 7
        aid = str(self.next_id)
        mov = int(moving if moving is not None else round(km * pace))
        a = {"id": aid, "name": name, "sport_type": sport, "start_local": f"{day}T{clock}:{self.next_id % 60:02d}"}
        if desc:
            a["description"] = desc
        if not (trainer or manual):
            a["location_summary"] = self.city
        a["is_trainer"] = trainer
        if tags:
            a["activity_tags"] = tags
        summary = {"distance": round(km * 1000, 1), "moving_time": mov, "elapsed_time": mov + 4 + pause,
                   "elevation_gain": 0 if trainer or manual else (elev if elev is not None else round(km * 6.5, 1)),
                   "avg_speed": round(km * 1000 / mov, 4) if mov and km else 0,
                   "max_speed": 0 if manual else round(km * 1000 / mov * 1.32, 3) if mov and km else 0}
        if not manual:
            summary["relative_effort"] = round(mov / 60 * RE_PER_MIN[kind])
        summary.update(total_calories=round(km * 66) if km else round(mov / 60 * 5), kudos_count=self.next_id % 5,
                       achievement_count=0, pr_count=0)
        a["summary"] = summary
        if not (trainer or manual):
            a["weather"] = {"condition": "Cloudy" if temp < 16 else "Clear", "wind_direction": "W", "temperature": temp,
                            "feels_like": temp - 1, "wind_speed": 2.8, "humidity": 68}
        self.acts.append(a)
        if hr:
            lap_rows, idx = [], 0
            for m, s, lap_hr in (laps or [(km * 1000, mov, hr[0])]):
                lap_rows.append({"elapsed_time": int(s), "moving_time": int(s), "start_index": idx, "end_index": idx + int(s) - 1,
                                 "distance": round(m, 1), "elevation_gain": round(m / 1000 * 5, 1),
                                 "avg_speed": round(m / s, 4), "max_speed": round(m / s * 1.2, 3),
                                 "avg_hr": lap_hr, "max_hr": lap_hr + 6, "avg_grade": 0.01})
                idx += int(s)
            self.perf[aid] = {"sport_type": sport, "has_heartrate": True, "has_device_watts": False,
                              "average_heartrate": hr[0], "max_heartrate": hr[1], "calories": summary["total_calories"],
                              "segment_efforts": [], "best_efforts": bests or [], "laps": lap_rows}
        return aid

    def search(self, keep=lambda a: True, total=None, order=None, first=None):
        acts = [a for a in self.acts if keep(a)]
        acts.sort(key=order or (lambda a: a["start_local"]), reverse=order is None)
        if order is not None and order.__name__ == "by_distance":
            acts.reverse()
        shown = acts[:first] if first else acts
        return {"activities": shown, "total_count": total if total is not None else len(acts), "offset": 0,
                "has_next_page": len(shown) < (total if total is not None else len(acts)), "value_units": UNITS}


def by_distance(a):
    return a["summary"]["distance"]


def is_run(a):
    return a["sport_type"] in ("Run", "TrailRun", "VirtualRun")


def since(days):
    cut = str(TODAY - timedelta(days=days))
    return lambda a: a["start_local"][:10] >= cut


def effort(kind, secs, d, aid, year=None):
    return {"sport": "Run", "best_effort_type": kind, "value": secs, "unit": "seconds",
            "year": year or int(d[:4]), "date": d, "activity_id": aid}


def zones(max_hr, sample_type, sample_time, speeds):
    hr = [round(max_hr * f) for f in (0.65, 0.81, 0.89, 0.97)]
    return {"heart_rate_zones": [{"min": 0, "max": hr[0]}, {"min": hr[0] + 1, "max": hr[1]}, {"min": hr[1] + 1, "max": hr[2]},
                                 {"min": hr[2] + 1, "max": hr[3]}, {"min": hr[3] + 1}],
            "heart_rate_zone_source": "MaxHeartRate",
            "run_zones": [{"min": lo, "max": hi} if hi else {"min": lo} for lo, hi in zip([0] + speeds, speeds + [None])],
            "run_zone_source": "RacePace",
            "sample_race_pace": {"best_effort_type": sample_type, "time": sample_time, "is_estimated": False}}


def write(case, files, notes):
    out = ROOT / case / "files" / "strava"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*"):
        old.unlink()
    lines = ["# Saved Strava connector responses", "",
             "There is no live Strava connection in this test. Each file below is the JSON one connector call returned",
             "for this athlete. Values are raw SI units (metres, seconds, m/s), as the connector returns them by default.",
             f"Today is {TODAY:%A %-d %B %Y}.", "", "| File | Connector call it stands for |", "|---|---|"]
    for name, (call, payload) in files.items():
        (out / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
        lines.append(f"| `{name}` | {call} |")
    lines += ["", "Nothing else is available offline (no streams, no gear, no other activities' details).", ""] + notes
    (out / "INDEX.md").write_text("\n".join(lines) + "\n")
    print(f"{case}: {len(files) + 1} files")


def monday(week):                       # week 0 = the Monday 12 weeks before this week's Monday
    return date(2026, 3, 9) + timedelta(days=7 * week)


def day(week, dow):
    return str(monday(week) + timedelta(days=dow))


RUN_TYPES = 'sport_types ["Run","TrailRun","VirtualRun"]'
OTHER = ('`search_activities`, sport_types ["Ride","VirtualRide","GravelRide","MountainBikeRide","Swim","Hike","WeightTraining",'
         '"Workout","Crossfit","HighIntensityIntervalTraining","Rowing","NordicSki","Elliptical","Yoga","Pilates"], '
         "start_date_min 2026-05-05, moving_time_min 1200, is_commute false")


def common_files(log, profile, zone, efforts, total_12m, total_all, first_run, extra_perf_note=""):
    files = {
        "get_athlete_profile.json": ("`get_athlete_profile`", profile),
        "get_athlete_zones.json": ("`get_athlete_zones`", zone),
        "search_activities.runs_last_12_weeks.json": (
            f"`search_activities`, {RUN_TYPES}, start_date_min 2026-03-09, include_tags true, first 100",
            log.search(lambda a: is_run(a) and a["start_local"][:10] >= "2026-03-09")),
        "search_activities.longest_runs_12_months.json": (
            f"`search_activities`, {RUN_TYPES}, start_date_min 2025-06-02, sort_field DISTANCE, first 5",
            log.search(lambda a: is_run(a) and since(365)(a), total=total_12m, order=by_distance, first=5)),
        "search_activities.first_run.json": (
            f"`search_activities`, {RUN_TYPES}, sort_field START_DATE, sort_descending false, first 1",
            {"activities": [first_run], "total_count": total_all, "offset": 0, "has_next_page": True, "value_units": UNITS}),
        "search_activities.races_18_months.json": (
            f'`search_activities`, {RUN_TYPES}, tags ["RACE"], start_date_min 2024-12-02, include_tags true, first 20',
            log.search(lambda a: is_run(a) and "Race" in a.get("activity_tags", []))),
        "get_athlete_best_efforts.json": (
            '`get_athlete_best_efforts`, sports ["Run"], years [2026, 2025], best_effort_types '
            '["Fastest5k","Fastest10k","FastestHalfMarathon","FastestMarathon"]',
            {"sports": ["Run"], "all_time": False, "efforts": efforts}),
        "search_activities.other_sports_4_weeks.json": (OTHER, log.search(lambda a: not is_run(a) and since(28)(a))),
    }
    for aid, payload in log.perf.items():
        act = next(a for a in log.acts if a["id"] == aid)
        files[f"get_activity_performance.{aid}.json"] = (
            f'`get_activity_performance`, activity_id {aid} ("{act["name"]}", {act["start_local"][:10]})', payload)
    return files


def old_run(d, km, mov, name, city, aid, tags=None, desc=None):
    a = {"id": aid, "name": name, "sport_type": "Run", "start_local": f"{d}T09:05:12", "location_summary": city, "is_trainer": False,
         "summary": {"distance": km * 1000, "moving_time": mov, "elapsed_time": mov + 5, "elevation_gain": round(km * 6, 1),
                     "avg_speed": round(km * 1000 / mov, 4), "max_speed": round(km * 1000 / mov * 1.3, 3),
                     "relative_effort": round(mov / 60 * (3.2 if tags else 1.0)), "total_calories": round(km * 66),
                     "kudos_count": 3, "achievement_count": 2, "pr_count": 1}}
    if tags:
        a["activity_tags"] = tags
    if desc:
        a["description"] = desc
    return a


# ---------------------------------------------------------------------------------------------------------
def maya():
    """Imperial units, 5 runs a week around 33 mi, a half marathon six weeks ago, marathon ahead."""
    g = Log(9100000000, "Madison, Wisconsin")
    easy, longp = 348, 356                                   # s/km: about 9:20 and 9:33 per mile
    weeks = [  # (tue, wed workout km, wed name, fri, sat or None, sun long)
        (8.0, 11.3, "Tempo 3x10min", 8.0, 6.4, 17.7), (8.1, 11.5, "6x800m", 8.0, 6.5, 19.3),
        (8.0, 11.3, "Tempo 4 miles", 8.2, 6.4, 20.9), (8.0, 9.7, "5x1000m", 8.0, None, 16.1),
        (8.1, 11.3, "Tempo 2x15min", 8.0, 6.4, 19.4), None, None,
        (8.0, 9.7, "Fartlek 8x1min", 8.0, 6.4, 17.7), (8.1, 11.3, "Tempo 3x10min", 8.0, 6.5, 19.3),
        (8.05, 11.3, "6x800m", 8.0, 6.4, 20.9), (8.0, 11.5, "Tempo 4 miles", 8.0, None, 21.7),
        (8.0, 11.3, "5x1000m", 8.1, 6.4, 22.6)]
    for w, row in enumerate(weeks):
        if row is None:
            continue
        tue, wed, wname, fri, sat, sun = row
        if w == 9:                                           # treadmill run saved by the watch and by the gym app
            for clock, nm in (("06:31", "Treadmill"), ("06:33", "Indoor run (gym app)")):
                g.add(day(w, 1), clock, tue, easy + 6, nm, trainer=True)
        else:
            hr = (139, 152) if w == 11 else None
            g.add(day(w, 1), "06:40", tue, easy, "Morning Run", hr=hr, temp=9 + w)
        laps = None
        if w == 10:                                          # 4-mile tempo with programmed laps
            laps = [(3200, 1120, 141), (6440, 1870, 166), (1860, 660, 148)]
        if w == 11:                                          # the workout was uploaded twice: watch + phone
            g.add(day(w, 2), "18:05", wed, 322, wname, "workout", tags=["Workout"])
            g.add(day(w, 2), "18:06", wed - 0.2, 325, "Evening Run", "easy")
        else:
            g.add(day(w, 2), "18:05", wed, 322, wname, "workout", tags=["Workout"] if w % 2 else None,
                  hr=(158, 172) if laps else None, laps=laps, temp=12 + w)
        g.add(day(w, 4), "06:45", fri, easy + 3, "Morning Run", hr=(141, 150) if w == 11 else None, temp=8 + w)
        if sat:
            g.add(day(w, 5), "08:10", sat, easy + 8, "Easy shakeout", hr=(137, 146) if w == 11 else None, temp=11 + w)
        pause = 1560 if w == 10 else 20
        g.add(day(w, 6), "08:02", sun, longp, "Long run" + (" + coffee stop" if w == 10 else ""), "long",
              tags=["LongRun"] if w in (2, 8, 11) else None, pause=pause, hr=(146, 158) if w == 11 else None, temp=10 + w)
    # week 5: taper and the race; week 6: recovery
    g.add(day(5, 1), "06:40", 8.0, easy, "Morning Run")
    g.add(day(5, 3), "18:10", 8.0, 338, "4x2min at half pace", "workout")
    g.add(day(5, 5), "09:00", 5.0, easy + 10, "Shakeout")
    g.add(day(5, 6), "06:35", 2.1, 372, "Warm-up", temp=7)
    race = g.add(day(5, 6), "07:00", 21.34, 0, "Lakefront Half Marathon", "race", tags=["Race"], moving=6448,
                 desc="Official time 1:47:30. Negative split, felt strong to the end!", hr=(168, 181), temp=8,
                 bests=[{"name": "Fastest5k", "type_value": "Fastest5k", "display_text": "5K", "value": 1475, "unit": "seconds"},
                        {"name": "Fastest10k", "type_value": "Fastest10k", "display_text": "10K", "value": 2990, "unit": "seconds"},
                        {"name": "FastestHalfMarathon", "type_value": "FastestHalfMarathon", "display_text": "Half-Marathon",
                         "value": 6398, "unit": "seconds"}])
    g.add(day(6, 2), "18:00", 6.4, easy + 14, "Recovery jog")
    g.add(day(6, 4), "06:45", 8.0, easy + 6, "Morning Run")
    g.add(day(6, 6), "08:05", 12.9, longp + 4, "Easy long-ish", "long")
    # other sports
    for w in range(8, 12):
        g.add(day(w, 0), "17:30", 28.0, 0, "Evening Ride", "other", sport="Ride", moving=4500, elev=180)
        g.add(day(w, 3), "07:00", 0, 0, "Yoga", "other", sport="Yoga", moving=2700, trainer=True)
    g.add(day(10, 5), "09:30", 9.5, 0, "Hike with friends", "other", sport="Hike", moving=7900, elev=420)
    # earlier races (outside the 12-week window)
    g.acts.append(old_run("2025-10-05", 21.2, 6730, "Fall Classic Half", g.city, "8700000011", ["Race"], "1:52:10 official"))
    g.acts.append(old_run("2025-09-14", 10.06, 2935, "Capitol 10K", g.city, "8600000042", ["Race"], "48:55!"))
    efforts = [effort("Fastest5k", 1475, day(5, 6), race), effort("Fastest5k", 1432, "2025-09-14", "8600000042"),
               effort("Fastest10k", 2990, day(5, 6), race), effort("Fastest10k", 2921, "2025-09-14", "8600000042"),
               effort("FastestHalfMarathon", 6398, day(5, 6), race), effort("FastestHalfMarathon", 6702, "2025-10-05", "8700000011")]
    profile = {"id": 91000001, "first_name": "Maya", "last_name": "Example", "measurement_preference": "Imperial", "gender": "Woman",
               "weight": 61, "weight_display": "134.5 lb", "location": {"city": "Madison", "state": "Wisconsin", "country": "USA"},
               "current_focus": {"id": "5100001", "focus_type": "TrainForEvent", "open_text": "Chicago Marathon",
                                 "expires_at_local": "2026-10-11T23:59:59"}}
    zone = zones(186, "Fastest10k", "49m 10s", [2.62, 3.02, 3.36, 3.58, 3.81])
    first = old_run("2021-03-14", 3.2, 1290, "First run!", g.city, "5000000001")
    write("marathon-plan-imperial", common_files(g, profile, zone, efforts, 228, 1041, first), [])


def tom():
    """Metric, about 40 km a week until a calf strain, five weeks off, three short runs back."""
    g = Log(9200000000, "Lyon, France")
    easy = 365
    weeks = [(8.0, 9.5, "6x3min", 7.0, 14.0), (8.2, 10.0, "Tempo 20min", 7.1, 15.0), (8.0, 9.6, "5x1km", None, 15.2),
             (8.1, 10.2, "Tempo 2x12min", 7.0, 16.0), (8.0, 9.8, "6x800m", 7.2, 14.1), (8.0, 9.9, "Tempo 25min", 7.0, 16.2)]
    for w, (tue, thu, tname, sat, sun) in enumerate(weeks):
        g.add(day(w, 1), "07:10", tue, easy, "Footing", hr=(141, 150) if w == 5 else None, temp=8 + w)
        g.add(day(w, 3), "18:30", thu, 330, tname, "workout", temp=12 + w)
        if sat:
            g.add(day(w, 5), "09:15", sat, easy + 5, "Footing du samedi", temp=10 + w)
        g.add(day(w, 6), "09:00", sun, easy + 4, "Sortie longue", "long", desc="Mollet qui tire sur la fin" if w == 5 else None,
              temp=11 + w)
    g.add(day(2, 5), "08:35", 2.1, 390, "Échauffement", temp=9)
    park = g.add(day(2, 5), "09:00", 5.02, 0, "parkrun", "race", tags=["Race"], moving=1432, desc="23:52, record sur 5 km",
                 hr=(172, 181), temp=10)
    # the break: nothing from 20 April to 23 May, then three short runs
    g.add("2026-05-24", "10:05", 4.1, 405, "Reprise en douceur", desc="Première sortie depuis la blessure. Mollet OK.", hr=(150, 158), temp=19)
    g.add("2026-05-28", "07:20", 5.2, 400, "Footing", hr=(152, 160), temp=17)
    g.add("2026-05-31", "09:30", 5.0, 396, "Footing du dimanche", hr=(151, 161), temp=21)
    # cross-training during the break
    for d, mins in (("2026-05-05", 50), ("2026-05-07", 65), ("2026-05-10", 70), ("2026-05-12", 45), ("2026-05-14", 60),
                    ("2026-05-17", 75), ("2026-05-19", 50), ("2026-05-21", 60), ("2026-05-26", 55), ("2026-05-30", 60)):
        g.add(d, "18:00", mins * 0.45, 0, "Sortie vélo", "other", sport="Ride", moving=mins * 60, elev=mins * 3)
    for d in ("2026-05-06", "2026-05-13", "2026-05-20", "2026-05-27"):
        g.add(d, "12:30", 0, 0, "Renfo mollets et gainage", "other", sport="Workout", moving=1500, trainer=True)
    g.acts.append(old_run("2025-09-06", 10.08, 2962, "10 km de la ville", g.city, "8600000910", ["Race"], "49:30 officiel"))
    efforts = [effort("Fastest5k", 1432, day(2, 5), park), effort("Fastest5k", 1421, "2025-09-06", "8600000910"),
               effort("Fastest10k", 3118, day(3, 3), "9200000113"), effort("Fastest10k", 2962, "2025-09-06", "8600000910")]
    profile = {"id": 92000001, "first_name": "Tom", "last_name": "Exemple", "measurement_preference": "Metric", "gender": "Man",
               "weight": 74, "weight_display": "74.0 kg", "location": {"city": "Lyon", "state": "", "country": "France"}}
    zone = zones(182, "Fastest10k", "49m 30s", [2.6, 3.0, 3.34, 3.56, 3.79])
    first = old_run("2023-01-08", 4.0, 1680, "Premier footing", g.city, "6100000001")
    write("return-from-break-10k", common_files(g, profile, zone, efforts, 171, 512, first), [])


def lena():
    """Check-in: two plan weeks done, one lost to the flu, one easy run back."""
    g = Log(9300000000, "Leeds, England")
    easy = 390
    base = [(7.0, 8.4, 5.0, 12.0), (7.2, 8.5, 5.1, 12.4), (7.0, 8.8, 5.0, 13.0), (7.1, 8.0, 5.0, 12.2), (7.0, 8.6, 5.2, 13.0)]
    for i, (tue, thu, sat, sun) in enumerate(base):          # weeks of 6 April to 4 May, before the plan
        w = i + 4
        g.add(day(w, 1), "06:50", tue, easy, "Easy run", temp=7 + i)
        g.add(day(w, 3), "18:15", thu, 352, ["Fartlek", "Hills x8", "Tempo 15min", "Fartlek", "3x6min"][i], "workout", temp=10 + i)
        g.add(day(w, 5), "08:30", sat, easy + 6, "Easy + strides", temp=9 + i)
        g.add(day(w, 6), "09:00", sun, easy + 3, "Long run", "long", temp=10 + i)
    race = g.add(day(4, 6) if False else "2026-04-12", "09:30", 10.05, 0, "Spring 10K", "race", tags=["Race"], moving=3210,
                 desc="53:30 chip time", hr=(171, 180), temp=9)
    g.acts = [a for a in g.acts if not (a["start_local"].startswith("2026-04-12") and a["name"] == "Long run")]
    # plan week 1 (11-17 May) and week 2 (18-24 May): done as written
    g.add("2026-05-12", "06:50", 7.1, easy, "Easy run", temp=12)
    g.add("2026-05-14", "18:15", 9.2, 0, "3x8min threshold", "workout", tags=["Workout"], moving=3190, hr=(156, 172), temp=15,
          laps=[(2000, 780, 138), (1500, 480, 165), (290, 120, 150), (1510, 480, 167), (285, 120, 152), (1490, 480, 169), (2125, 730, 146)])
    g.add("2026-05-16", "08:30", 5.0, easy + 6, "Easy + strides", temp=13)
    g.add("2026-05-17", "09:00", 14.1, easy + 2, "Long run", "long", temp=14)
    ref = g.add("2026-05-19", "06:50", 7.0, 390, "Easy run", hr=(139, 149), temp=13)
    g.add("2026-05-21", "18:15", 9.9, 0, "4x8min threshold", "workout", tags=["Workout"], moving=3470, hr=(159, 176), temp=17,
          laps=[(2000, 785, 139), (1505, 480, 167), (290, 120, 153), (1490, 480, 169), (285, 120, 155), (1500, 480, 171),
                (280, 120, 156), (1480, 480, 172), (1070, 405, 150)])
    g.add("2026-05-23", "08:30", 5.1, easy + 5, "Easy + strides", temp=15)
    g.add("2026-05-24", "09:00", 15.0, easy + 4, "Long run", "long", temp=16)
    # plan week 3 (25-31 May): flu, nothing. Monday 1 June: first run back
    back = g.add("2026-06-01", "07:05", 5.0, 410, "Back at it", desc="First run after the flu, legs heavy", hr=(148, 159), temp=14)
    for d in ("2026-05-06", "2026-05-13", "2026-05-20"):
        g.add(d, "19:00", 0, 0, "Gym: legs and core", "other", sport="WeightTraining", moving=2700, trainer=True)
    efforts = [effort("Fastest5k", 1570, "2026-04-12", race), effort("Fastest10k", 3198, "2026-04-12", race),
               effort("Fastest10k", 3345, "2025-10-19", "8700000555"), effort("FastestHalfMarathon", 7410, "2025-11-16", "8800000101")]
    g.acts.append(old_run("2025-11-16", 21.15, 7402, "Autumn Half", g.city, "8800000101", ["Race"], "2:03:30"))
    profile = {"id": 93000001, "first_name": "Lena", "last_name": "Example", "measurement_preference": "Metric", "gender": "Woman",
               "weight": 58, "weight_display": "58.0 kg", "location": {"city": "Leeds", "state": "", "country": "United Kingdom"},
               "current_focus": {"id": "5300001", "focus_type": "TrainForEvent", "open_text": "Summer half under 1:58",
                                 "expires_at_local": "2026-07-19T23:59:59"}}
    zone = zones(184, "Fastest10k", "53m 30s", [2.42, 2.79, 3.1, 3.31, 3.52])
    first = old_run("2024-02-11", 3.0, 1320, "Couch to 5K week 1", g.city, "6900000001")
    files = common_files(g, profile, zone, efforts, 187, 371, first)
    files["search_activities.runs_last_8_weeks.json"] = (
        f"`search_activities`, {RUN_TYPES}, start_date_min 2026-04-06, include_tags true, first 100",
        g.search(lambda a: is_run(a) and a["start_local"][:10] >= "2026-04-06"))
    del files["search_activities.runs_last_12_weeks.json"]
    write("checkin-after-illness", files, ["The plan being followed is in `plan.md`, next to this folder."])


if __name__ == "__main__":
    maya(), tom(), lena()
