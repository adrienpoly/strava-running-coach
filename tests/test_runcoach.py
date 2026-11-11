"""Tests for scripts/runcoach.py and the repository's generated files.

    python3 -m unittest discover -s tests -v
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "runcoach.py"
sys.path.insert(0, str(SCRIPT.parent))
import runcoach as rc  # noqa: E402


def run(*args, stdin=""):
    out = subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True)
    return out.stdout + out.stderr


class PaceModel(unittest.TestCase):
    # Equivalent race times from Daniels' published VDOT tables.
    TABLE = {30: ("30:40", "1:03:46", "2:21:04", "4:49:17"), 40: ("24:08", "50:03", "1:50:59", "3:49:45"),
             50: ("19:57", "41:21", "1:31:35", "3:10:49"), 60: ("17:03", "35:22", "1:18:09", "2:43:25")}

    def test_equivalents_match_published_tables(self):
        for vd, times in self.TABLE.items():
            for dist, expected in zip(("5k", "10k", "hm", "m"), times):
                got, want = rc.equiv(vd, rc.KM[dist]), rc.secs(expected)
                self.assertLess(abs(got - want) / want, 0.003, f"VDOT {vd} {dist}: {rc.hms(got)} vs {expected}")

    def test_round_trip(self):
        for km, s in ((5, 1500), (10, 3187), (21.0975, 7287), (42.195, 14400)):
            self.assertAlmostEqual(rc.equiv(rc.vdot(km, s), km), s, delta=0.5)

    def test_threshold_and_interval_paces(self):
        for vd, t, i in ((40, "5:06", "4:41"), (50, "4:15", "3:55"), (60, "3:40", "3:23")):
            self.assertAlmostEqual(60000 / rc.speed(0.88 * vd), rc.secs(t), delta=1.5)
            self.assertAlmostEqual(60000 / rc.speed(0.975 * vd), rc.secs(i), delta=1.5)


class Paces(unittest.TestCase):
    def test_anchor_is_best_fresh_result(self):
        out = run("paces", "--today", "2026-06-02", "--result", "hm,1:47:30,2026-04-19,race",
                  "--result", "5k,26:30,2026-05-20,split", "--result", "10k,44:00,2025-01-01,old")
        self.assertIn("ANCHOR  VDOT 41.5 from hm 1:47:30", out)

    def test_stale_anchor_is_flagged(self):
        out = run("paces", "--today", "2026-06-02", "--result", "10k,50:00,2025-06-01")
        self.assertIn("stale", out)

    def test_goal_verdicts(self):
        base = ("paces", "--today", "2026-06-02", "--result", "hm,2:00:00,2026-05-24")
        self.assertIn("-> already there", run(*base, "--goal", "hm,2:05:00", "--weeks", "12"))
        self.assertIn("-> realistic", run(*base, "--goal", "hm,1:58:00", "--weeks", "12"))
        self.assertIn("-> stretch", run(*base, "--goal", "hm,1:54:30", "--weeks", "12"))
        self.assertIn("-> long shot", run(*base, "--goal", "hm,1:45:00", "--weeks", "12"))

    def test_layoff_discounts_fitness(self):
        base = ("paces", "--today", "2026-06-02", "--result", "5k,23:52,2026-03-28", "--goal", "10k,49:59", "--weeks", "8")
        self.assertIn("already there", run(*base))
        off = run(*base, "--layoff", "34")
        self.assertIn("LAYOFF  34 d", off)
        self.assertRegex(off, r"VDOT 40\.5 -> 36\.9")
        self.assertNotIn("already there", off)
        self.assertRegex(run(*base, "--layoff", "34", "--cross-trained"), r"VDOT 40\.5 -> 38\.7")

    def test_label_may_contain_commas(self):
        out = run("paces", "--today", "2026-06-02", "--result", "5k,23:52,2026-03-28,parkrun, official time")
        self.assertIn("parkrun, official time", out)

    def test_miles(self):
        out = run("paces", "--unit", "mi", "--today", "2026-06-02", "--result", "hm,1:47:30,2026-04-19")
        self.assertIn("(8:12/mi)", out)
        self.assertRegex(out, r"threshold 7:5\d-8:0\d")


ROWS = """start_local,distance,moving_time,elapsed_time,elevation_gain,relative_effort,kind
2026-05-31T09:00:00,16000,5800,5900,90,150,long
2026-05-28T18:30:00,8000,2600,2610,30,80,workout
2026-05-26T07:00:00,6000,2200,2205,20,40,easy
2026-05-26T07:01:00,5900,2190,2195,0,,easy
2026-05-24T09:00:00,15000,5500,6500,80,140,long
2026-05-23T08:00:00,900,300,300,5,2,easy
2026-05-20T12:00:00,9000,4000,6400,50,120,other
2026-05-17T08:30:00,2000,780,790,10,8,easy
2026-05-17T09:00:00,10000,3000,3005,40,160,race
"""


class Digest(unittest.TestCase):
    def setUp(self):
        self.out = run("digest", "--since", "2026-05-04", "--today", "2026-06-02", stdin=ROWS)

    def week(self, monday):
        return next(line.split() for line in self.out.splitlines() if line.startswith(monday))

    def test_duplicate_upload_counted_once(self):
        self.assertIn("1 duplicate upload(s) dropped", self.out)
        self.assertEqual(self.week("2026-05-25")[3], "30.0")

    def test_volume_only_activities_are_not_sessions(self):
        # week of 18 May: long run (session), 900 m jog and the 'other' activity (volume only)
        w = self.week("2026-05-18")
        self.assertEqual((w[1], w[3]), ("1", "24.9"))
        # week of 11 May: the 13-minute warm-up before the race is volume only
        w = self.week("2026-05-11")
        self.assertEqual((w[1], w[3], w[-1]), ("1", "12.0", "race"))

    def test_long_pause_flag_and_ceiling(self):
        self.assertIn("run(s) with long pauses", self.out)
        self.assertIn("ceiling for the next long run 17.6 km", self.out)

    def test_break_is_reported(self):
        rows = ("2026-03-10T07:00:00,8000,2800,2800,0,,easy\n2026-03-15T07:00:00,15000,5400,5400,0,,long\n"
                "2026-05-24T07:00:00,4000,1600,1600,0,,easy\n2026-05-28T07:00:00,5000,2000,2000,0,,easy\n")
        out = run("digest", "--since", "2026-03-09", "--today", "2026-06-02", stdin=rows)
        self.assertIn("BREAK: no run from 2026-03-16 to 2026-05-23 (69 d)", out)
        self.assertIn("before the break (1 wk): 23.0 km/wk, 2 sessions/wk", out)
        self.assertIn("ceiling for the next long run 6.0 km", out)

    def test_miles_and_bad_rows(self):
        out = run("digest", "--since", "2026-05-04", "--today", "2026-06-02", "--unit", "mi", stdin=ROWS)
        self.assertIn("ceiling for the next long run 10.9 mi", out)
        self.assertIn("bad row", run("digest", "--since", "2026-05-04", stdin="2026-05-31,09:00,16000,x\n"))

    def test_leading_partial_week_is_dropped(self):
        out = run("digest", "--since", "2026-05-06", "--today", "2026-06-02", stdin=ROWS)
        self.assertNotIn("2026-05-04", out)


def check(recent, long, rows, *extra):
    return run("check", "--recent", recent, "--recent-long", str(long), *extra, stdin="\n".join(rows) + "\n")


class Check(unittest.TestCase):
    def test_steady_build_is_clean(self):
        out = check("28,30,29,30", 11, ["1,33,12", "2,36,13", "3,39,14.3", "4,30,11,down", "5,42,15.5"])
        self.assertNotIn("SPIKE", out)
        self.assertNotIn("ceiling", out)

    def test_spikes_and_ceiling(self):
        out = check("15,12,18,15", 8, ["1,20,12", "2,26,15", "3,32,19"])
        self.assertEqual(out.count("SPIKE"), 3)
        self.assertEqual(out.count("long run over the ceiling"), 3)

    def test_small_absolute_steps_are_not_spikes(self):
        out = check("0,0,4,10", 5.2, ["1,14,6", "2,18,7", "3,22,8", "4,20,7,down", "5,24,9"])
        self.assertNotIn("SPIKE", out)
        self.assertNotIn("ceiling", out)
        self.assertIn("recent weeks are low", check("40,41,0,0,0,4,10", 5.2, ["1,14,6"]))

    def test_returning_to_recent_volume_is_not_a_spike(self):
        self.assertNotIn("SPIKE", check("22,31,13,35", 21.9, ["1,14,7,recovery", "2,20,10", "3,25,13", "4,28,15", "5,30,16"]))
        self.assertIn("SPIKE", check("30,15,15,15", 9, ["1,32,10"]))

    def test_calendar_and_taper(self):
        rows = ["1,30,14", "2,32,15", "3,20,10,taper", "4,10,5,race"]
        ok = check("28,29,30,29", 14, rows, "--start", "2026-06-01", "--race", "2026-06-28")
        self.assertIn("is in the last plan week: OK", ok)
        self.assertIn("2026-06-22 to 2026-06-28", ok)
        self.assertIn("is NOT in the last plan week", check("28,29,30,29", 14, rows, "--start", "2026-06-01", "--race", "2026-07-05"))
        self.assertIn("no visible taper", check("28,29,30,29", 14, ["1,30,14", "2,32,15", "3,10,5,race"]))
        self.assertIn("warning", check("28,29,30,29", 14, rows, "--start", "2026-06-02"))

    def test_recent_long_run_ages_out_by_date(self):
        rows = ["1,26,10,down", "2,33,12", "3,36,14", "4,39,16"]
        loose = check("33,35,37,0", 15, rows, "--start", "2026-06-01")
        self.assertNotIn("ceiling", loose)               # without a date the 15 km is assumed to be last week's
        dated = check("33,35,37,0", 15, rows, "--start", "2026-06-01", "--recent-long-date", "2026-05-24")
        # the 16 km on 28 June comes 35 days after the 15 km of 24 May, so only the plan's own 14 km counts
        self.assertIn("long run over the ceiling (15.4)", dated)
        self.assertEqual(dated.count("ceiling"), 1)
        self.assertIn("recent weeks are low", dated)

    def test_fifth_build_week_note(self):
        out = check("30,30,30,30", 12, [f"{i},{30 + 2 * i},{12 + i}" for i in range(1, 7)])
        self.assertIn("5th build week in a row", out)


def streams(segments, step=100, hr=None):
    """Streams for a run made of (metres, seconds per km) segments, one sample every `step` metres."""
    t, d, out = 0.0, 0, {"time": [0], "distance": [0.0]}
    for metres, pace in segments:
        for _ in range(metres // step):
            t, d = t + pace * step / 1000, d + step
            out["time"].append(round(t))
            out["distance"].append(float(d))
    if hr:
        out["heart_rate"] = [hr(x) for x in out["distance"]]
    return out


def activity(data, *args):
    return run("activity", *args, stdin=data if isinstance(data, str) else json.dumps(data))


class Activity(unittest.TestCase):
    def test_even_run(self):
        out = activity(streams([(10000, 360)], hr=lambda x: 140), "--zones", "120,150,165,178")
        self.assertIn("ACTIVITY  10.00 km in 1:00:00 = 6:00/km", out)
        self.assertEqual(len(re.findall(r"^ +\d+ +6:00 +140$", out, re.M)), 10)
        self.assertIn("+0.0% = even", out)
        self.assertIn("speed per heartbeat down 0.0%", out)
        self.assertIn("Z1 0% | Z2 100% | Z3 0%", out)
        self.assertNotIn("NOTE", out)

    def test_fade_fast_start_and_drift(self):
        data = streams([(1000, 300), (9000, 330), (10000, 380)], hr=lambda x: 150 + x / 1000)
        out = activity(data, "--kind", "long", "--prior-longest", "16000")
        self.assertIn("positive split (slowed)", out)
        self.assertIn("NOTE  fast start: first km in 5:00", out)
        self.assertRegex(out, r"NOTE  fade: last quarter 1\d\.\d% slower than the first half")
        self.assertRegex(out, r"speed per heartbeat down 1\d\.\d%")
        self.assertIn("+25% -> over the 10% line (17.6)", out)
        self.assertIn("within the 10% line", activity(data, "--kind", "long", "--prior-longest", "19000"))
        self.assertNotIn("DRIFT", activity(data, "--kind", "race"))

    def test_stop_is_found_and_counted_in_the_pace(self):
        data = streams([(5000, 360)])
        data["time"] = [x + (120 if i > 25 else 0) for i, x in enumerate(data["time"])]
        out = activity(data)
        self.assertIn("STOPS  about 2:00 stopped or walking, at km 2.5", out)
        self.assertRegex(out, r" 3 +8:00  stop or walk")
        self.assertIn("no heart rate", out)

    def test_miles_rows_and_other_json_shapes(self):
        data = streams([(8046, 373)], step=149)                    # 5 miles at 10:00 per mile
        out = activity(data, "--unit", "mi")
        self.assertRegex(out, r"ACTIVITY  5\.00 mi in 50:0\d = 10:00/mi")
        rows = "time,distance\n" + "\n".join(f"{t},{d}" for t, d in zip(data["time"], data["distance"]))
        self.assertEqual(activity(rows, "--unit", "mi"), out)
        api = [{"type": k, "data": v} for k, v in data.items()]
        self.assertEqual(activity(api, "--unit", "mi"), out)
        self.assertEqual(activity({"streams": data}, "--unit", "mi"), out)

    def test_bad_input(self):
        self.assertIn('need the "time" and "distance" streams', activity({"heart_rate": [140, 141]}))
        self.assertIn("nothing to analyse", activity(""))
        self.assertIn("bad lap", run("activity", "--laps", "1000"))

    def test_reps_are_guessed_from_laps(self):
        laps = ["2000:780:138", "1500:480:165", "290:120:150", "1510:480:167", "285:120:152", "1490:480:169", "2125:730:146"]
        out = run("activity", "--kind", "workout", "--target", "5:15-5:25", "--laps", *laps)
        self.assertIn("REPS  3 (laps 2, 4, 6; guessed from pace, correct with --reps): 4.50 km in 24:00, mean 5:20/km", out)
        self.assertIn("recoveries: 2, mean 2:00", out)
        self.assertIn("3 in range, 0 faster, 0 slower", out)
        self.assertIn("HR 165 -> 169", out)

    def test_reps_without_warm_up_laps_and_with_a_fade(self):
        laps = ["1000:245", "400:150", "1000:257", "400:170", "1000:266", "400:190", "1000:284"]
        out = run("activity", "--kind", "workout", "--target", "4:20-4:27", "--laps", *laps)
        self.assertIn("REPS  4 (laps 1, 3, 5, 7;", out)
        self.assertIn("last against first +15.9%", out)
        self.assertIn("1 in range, 2 faster, 1 slower", out)       # 4:05 and 4:17 fast, 4:26 in, 4:44 slow

    def test_auto_laps_and_named_reps(self):
        auto = run("activity", "--laps", "1000:340", "1000:338", "1000:335", "1000:341", "600:200")
        self.assertIn("no clear repetitions", auto)
        self.assertNotIn("REPS", auto)
        named = run("activity", "--reps", "2,4", "--laps", "2000:780", "1500:480", "290:120", "1510:480", "2125:730")
        self.assertIn("REPS  2 (laps 2, 4):", named)

    def test_fixture_streams_tell_the_story_the_cases_rely_on(self):
        strava = ROOT / "evals" / "activity-long-run-fade" / "files" / "strava"
        out = activity(next(strava.glob("get_activity_streams.*.json")).read_text(), "--kind", "long", "--prior-longest", "16200")
        self.assertIn("ACTIVITY  21.10 km in 2:10:28", out)
        self.assertIn("STOPS  about 1:3", out)
        self.assertIn("+30% -> over the 10% line (17.8)", out)
        strava = ROOT / "evals" / "activity-race-fast-start" / "files" / "strava"
        out = activity(next(strava.glob("get_activity_streams.*.json")).read_text(), "--kind", "race", "--unit", "mi")
        self.assertRegex(out, r" 1 +7:40 ")
        self.assertIn("+9.1% = positive split (slowed)", out)


class GeneratedFiles(unittest.TestCase):
    def test_dist_is_in_sync(self):
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "build_dist.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_zip_has_the_skill_folder_at_its_root(self):
        import zipfile
        with zipfile.ZipFile(ROOT / "dist" / "strava-running-coach.zip") as z:
            self.assertEqual(sorted(z.namelist()), ["strava-running-coach/SKILL.md", "strava-running-coach/scripts/runcoach.py"])

    def test_embedded_script_extracts_cleanly(self):
        text = (ROOT / "dist" / "SKILL.md").read_text()
        blocks = re.findall(r"^```python\n(.*?)^```$", text, re.S | re.M)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0], SCRIPT.read_text())

    def test_fixtures_are_reproducible(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_fixtures", ROOT / "tools" / "make_fixtures.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        committed = {p.relative_to(ROOT / "evals"): p.read_text() for p in (ROOT / "evals").glob("*/files/strava/*")}
        with tempfile.TemporaryDirectory() as tmp:
            gen.ROOT = Path(tmp)
            for runner in gen.RUNNERS:
                runner()
            fresh = {p.relative_to(tmp): p.read_text() for p in Path(tmp).glob("*/files/strava/*")}
        self.assertEqual(fresh, committed)

    def test_skill_frontmatter(self):
        head = (ROOT / "SKILL.md").read_text().split("---")[1]
        self.assertIn("name: strava-running-coach", head)
        desc = re.search(r"^description: (.+)$", head, re.M).group(1)
        self.assertLessEqual(len(desc), 200)             # the Claude apps reject longer descriptions on upload
        self.assertNotRegex(desc, r"[<>]")


if __name__ == "__main__":
    unittest.main()
