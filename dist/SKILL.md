---
name: strava-running-coach
description: Running coach on a runner's Strava data. Use for running plans (5K to marathon), feedback on a run, workout or race, training read-outs, pace or goal questions, check-ins, even if Strava isn't named.
---

# Strava Running Coach

Coach runners from what they actually did. The Strava connector supplies the training log, the bundled script does the arithmetic, and you supply the judgement: what the numbers mean for this person and what to do next.

Four jobs, one foundation:

- **Plan**: build a training plan toward a race or a fitness goal (steps 1-8).
- **Check-in**: compare the plan with what Strava shows and adapt the coming weeks ("Check-in mode").
- **Read-out**: "how is my training going?", "what paces should I use?", "is my goal realistic?". Do steps 1-6 and answer the question. A plan is an offer here, not an obligation.
- **Activity feedback**: "how was my run?", "did I get that session right?", "what went wrong in my race?". One run, read against the runner's own recent running ("Activity feedback mode"). It needs six weeks of context, not steps 1-6.

Answer in the runner's language and units (`measurement_preference` in the Strava profile), and keep it clear which numbers Strava measured and which are your estimates.

## Principles

1. **Data first, questions second.** Pull Strava before asking anything, show the runner what you found, then ask only what data cannot know. A long interview before any value loses people, and self-reported training gets rounded up.
2. **The script does the arithmetic, you do the reading.** Weekly totals over dozens of activities, calendar dates and non-linear pace formulas are where eyeballing goes wrong. Never show a metric you did not compute.
3. **Strava logs are messy and context-blind.** Clean and classify before trusting a number (step 2), and confirm a surprising number with a second signal before telling runners something about themselves.
4. **Train from current fitness toward the goal**, never backwards from the goal time.
5. **Be honest about evidence.** Most plan-design rules are coaching conventions. Don't quote injury-risk percentages or promise safety; "What the evidence supports" lists what you can claim.
6. **Coach, not clinician.** See "Safety".

## Step 1 - Pull the data

Use the Strava connector tools (your environment may prefix the names). If there are none, or `eligibility` says the account is not eligible, say so in one sentence (the connector must be enabled, and Strava requires a subscription for it) and go to "Without Strava".

Run these together; all are read-only. "Run types" means `sport_types: ["Run","TrailRun","VirtualRun"]`.

| # | Call | What it gives you |
|---|---|---|
| 1 | `get_athlete_profile` | Units; `current_focus` (a goal hint that may have expired, so confirm it). Ignore weight. |
| 2 | `get_athlete_zones` | HR zones and pace zones, each with its source; `sample_race_pace` shows which race Strava's pace zones are built on. |
| 3 | `search_activities`: run types, `start_date_min` = the Monday 12 weeks before this week's Monday, `include_tags: true`, `first: 100` (page with `offset` while `has_next_page`) | The training log. |
| 4 | `search_activities`: run types, `start_date_min` = 12 months ago, `sort_field: "DISTANCE"`, `first: 5` | The year's longest runs, and `total_count` = runs in the last 12 months. |
| 5 | `search_activities`: run types, `sort_field: "START_DATE"`, `sort_descending: false`, `first: 1` | First run ever, and all-time `total_count`. |
| 6 | `search_activities`: run types, `tags: ["RACE"]`, `start_date_min` = 18 months ago, `first: 20`, `include_tags: true` | Races: the best fitness anchors. Races that were never tagged only show up in calls 3 and 4, so read names and descriptions there too. |
| 7 | `get_athlete_best_efforts`: `sports: ["Run"]`, `years: [this year, last year]`, `best_effort_types: ["Fastest5k","Fastest10k","FastestHalfMarathon","FastestMarathon"]` | Dated best efforts (the tool cannot do rolling windows, so filter by date yourself). |
| 8 | `search_activities`: `sport_types: ["Ride","VirtualRide","GravelRide","MountainBikeRide","Swim","Hike","WeightTraining","Workout","Crossfit","HighIntensityIntervalTraining","Rowing","NordicSki","Elliptical","Yoga","Pilates"]`, `start_date_min` = 4 weeks ago, `moving_time_min: 1200`, `is_commute: false`, `first: 40` | Other training: habits to schedule around, fitness that run volume does not show. |

Detail calls are large, so make a handful, each for a reason:

- `get_activity_performance` on 2-3 ordinary easy runs and on the latest race or hardest effort (average and max HR), and on a recent workout when its execution matters (laps mirror the workout when the watch was programmed; otherwise there is one lap).
- `get_activity_streams` only for a within-run question (a fade in a long run, the pacing of a race): ask for `["time","distance","heart_rate","altitude"]` at about 8 points per km and hand the result to `activity` ("Activity feedback mode"). Leave `velocity_smooth` alone: its samples are instantaneous and noisy.
- `get_gear` only if the runner asks about shoes. `get_training_plan` returns a link to a partner app, not data; skip it unless asked.

Widen call 3 to 26 or 52 weeks only when the last 12 are unrepresentative (injury, long break, or the runner says so).

## Step 2 - Clean and classify

Before any maths, read the run list and give each activity a `kind`. Names and descriptions are the best clue, in whatever language the runner writes:

- `race`: tagged Race, or the name or description says so.
- `workout`: tagged Workout, or the name shows structure ("6x800", "3x8min @5:30", tempo, fartlek, hills, seuil, fractionné, VMA...).
- `long`: tagged Long Run, or plainly the week's long run.
- `other`: not a continuous run, so pace means nothing: a fitness race with stations, a run-walk with children or a dog, manual entries of gym treadmill bits. Counted in volume only: not a session, not in pace statistics.
- `easy`: everything else.

Traps that are common in real logs:

- **Race times.** GPS distance usually reads long, so average pace reads fast and a GPS "best effort" on race day can be flattering. Use the official time over the official distance when the description gives it or the runner confirms it. A race whose watch kept running afterwards has a useless elapsed time; use the best effort for that distance instead. When the course itself ran long (a detour), give `paces` the distance actually covered in km. A watch that read long in a race reads long in training too: say so when you hand over paces.
- **Best efforts inside longer runs** (a 5K "best" set during a 10K race or a tempo run) are lower bounds, not all-out results. A best effort with a suspiciously round value may have been typed in by hand.
- **Duplicates**: one outing uploaded by two devices or apps. The script drops overlapping records; check its count.
- **Split outings**: warm-up, race and cool-down saved separately. The script counts runs under 10 minutes or 1.5 km, and short runs on a race day, as volume but not as sessions.
- **Moving vs elapsed time**: Strava's pace uses moving time, which flatters runs with long pauses.
- **Treadmill and manual entries** (`is_trainer`, no weather, round numbers): distance is approximate.
- **Weather and terrain**: look at `weather.temperature`, humidity and elevation gain before calling a slow run a bad run.
- **Untracked running**: ask once whether anything is missing (another app, a forgotten watch).
- **Privacy**: descriptions are the runner's private notes. Use them to classify and to pick up facts the plan needs (an official time, a niggle), without quoting the names and places in them back.

## Step 3 - Run the numbers

Get the script once per conversation. If you were given this skill's directory, extract it; otherwise write the block at the end of this file to `runcoach.py` exactly as it is.

```bash
sed -n '/^```python$/,/^```$/p' "<skill directory>/SKILL.md" | sed '1d;$d' > runcoach.py
```

**Load picture.** One line per run from call 3, with Strava's raw values (metres, seconds; leave `relative_effort` empty when absent) plus your `kind`:

```bash
python3 runcoach.py digest --since 2026-03-02 --today 2026-05-26 [--unit mi] <<'EOF'
start_local,distance,moving_time,elapsed_time,elevation_gain,relative_effort,kind
2026-05-24T09:02:11,16120.4,5710,5802,96.0,171,long
2026-05-21T18:30:40,8010.9,2650,2655,31.2,88,workout
EOF
```

`--since` is the `start_date_min` you used in call 3. All three subcommands take `--today`: pass the runner's local date every time, because result ages and week boundaries depend on it and sandbox clocks drift. The output is a weekly table (sessions, volume, time, elevation, longest run, hard sessions, relative effort) and a summary: baseline volume three ways, any break, run days, long-run ceiling, typical easy pace, flags.

**Fitness and paces.** Pass every credible result from the last year: races with official times, dated best efforts, each labelled for your own reading. The script anchors on the highest VDOT from the last 12 weeks, because results set inside longer runs are lower bounds. Leave out a GPS-flattered result when you have the official time for the same race.

```bash
python3 runcoach.py paces --today 2026-05-26 --result hm,1:58:40,2026-05-10,race \
  --result 5k,26:05,2026-04-18,"split in a tempo run" --goal hm,1:54:00 --weeks 14 [--unit mi]
```

Distances: `5k`, `10k`, `hm`, `m`, `mile`, or a number of km. `--weeks` is whole calendar weeks from today to race day, rounded down. Output: VDOT per result, the anchor, equivalent times and paces at 5K, 10K, half and marathon, training pace ranges, and a goal verdict.

If the runner stopped running after the anchor was set (injury, illness, a long break), add `--layoff DAYS` with the length of the break, whatever has happened since, plus `--cross-trained` when they kept cycling or similar (widen call 8 to cover the break before deciding). The script then discounts fitness by a rule of thumb, and every pace stays provisional until a test.

**Plan lint** (step 8): `python3 runcoach.py check`. **One run** ("Activity feedback mode"): `python3 runcoach.py activity`.

The script converts units itself (`--unit mi`). To quote a single Strava value in the runner's units, request it with `use_preferred_units: true` instead of converting in your head.

No code execution? See "Without code execution".

## Step 4 - Read the numbers like a coach

Work these out before you say anything:

- **Running age.** Call 5 says how long ago they started; calls 4 and 3 say how consistently they run now. A ten-year-old account with most of its runs in the last year belongs to a newer runner. Under about a year of consistent running, tissues lag behind fitness: fewer hard sessions, slower build.
- **Baseline volume.** Compare the last-4-week average, the 8-week median and the best 4-week block. When they agree, that is the baseline. When recent weeks are low because of a taper, a race, illness or holidays, the median and best block describe what the runner can absorb and the last 4 weeks describe where they are now; start between the two, closer to "now" after more than two low weeks. For hilly or trail runners and for slower runners, think in hours: time is the fairer measure of load.
- **Rhythm.** Median sessions per week and usual run days. The plan's default week should look like their real week.
- **Long run.** The longest run of the last 30 days sets the ceiling for the next one (step 7). If the longest run is more than half the week, the week hangs on one run: a short extra easy day is worth more than a longer long run.
- **Are easy runs easy?** Comparing the typical easy pace with the easy range from `paces` is only a prompt. Pace ranges derived from races mislead in both directions (an anchor from a long race run on low volume makes the easy range too slow; hills and heat slow real paces). Decide with heart rate from 2-3 ordinary easy runs: easy means zones 1-2 of Strava's five when the zones are believable, or, independent of zone settings, an average at or below roughly 85% of the average HR of a recent 10K race or 90% of a recent half marathon's (rule of thumb). Without HR, ask about the talk test. Tell a runner to slow down only when heart rate or effort says so, and when heart rate shows their usual pace is easy, print that pace as the fast end of their easy range.
- **Are the zones believable?** The zone source tells you how they were derived. Default zones are fixed fractions of a max HR (boundaries near 65/81/89/97%), so the implied max is about the zone-5 floor divided by 0.97. If recent all-out efforts go well past it, the zones are too low; if hard race finishes stay far below, too high. Say so, and suggest fixing it in Strava. Likewise, if `sample_race_pace` is old or slower than the current anchor, Strava's pace zones are stale.
- **Hard sessions.** How many per week, what kind (names), and whether they hit their targets (laps).
- **Fitness profile.** Compare VDOT across distances. Clearly lower at longer distances (about 1.5 points or more) means endurance is the limiter: volume, long runs and threshold work come first. The reverse means speed is. An anchor older than 12 weeks makes every pace provisional: schedule a test.
- **Other training** (call 8). Existing strength work or classes are habits to schedule around, not to duplicate. Regular cycling or swimming means the engine is ahead of the legs: set run volume by running history, not by fitness.
- **Flags** from the script: past spikes, long pauses, duplicates.

## Step 5 - Show the picture, ask what is missing

One message: the picture in a few lines, then only the questions the data cannot answer. Skip what the runner already said and what you already know about them from earlier in the conversation. If nobody is there to answer, list your assumptions in one short block and carry on.

Example picture (invented runner; adapt, don't copy):

> From Strava, last 12 weeks: 3 runs most weeks (Tue, Thu, Sun), about 31 km a week lately and 36 km at your best. Long run on Sundays, up to 17 km. One session with pace work most weeks. Your easy runs really are easy (HR around 138, against 164 in your 10K). That 10K in 51:20 suggests about 1:53 for a half today [estimate]. Running steadily for about two years. One gym session a week on top.

Then ask:

1. **Goal**: event or distance, date, and what success means (finish, a time, a best). Pre-fill from `current_focus` when it is still current.
2. **Availability**: runs per week they can sustain, impossible days, preferred long-run day (suggest their usual one).
3. **Body**: any pain or niggle now, injuries in the last 12 months.
4. **Blind spots**: untracked running, travel or shift work, the race's terrain. Age is optional: it only nudges recovery spacing.

## Step 6 - Goal reality check

Run `paces` with `--goal` and `--weeks`, and tell the truth kindly, with numbers: current equivalent, goal, gap, verdict (realistic, stretch, long shot). The verdict is a rule of thumb, so say so, and call a borderline one borderline.

- **Any time goal**: set an A goal and a B goal, and name a checkpoint about halfway where the goal is re-assessed: a tune-up race or time trial (for a marathon, usually a half 6-8 weeks out), or a controlled key session when an all-out effort is unwise (a return from injury). Until the checkpoint, train at current paces.
- **After a layoff**: the anchor describes the runner before the break. Use `--layoff`, say plainly that today's level is an estimate, and make the checkpoint the first real measurement.
- **Stepping up in distance**: equivalents for distances longer than the anchor assume the endurance exists. For a half or a marathon predicted from shorter races on modest volume, expect slower (in a survey of about 2,300 recreational runners the standard formula was at least 10 minutes too fast for half of the marathoners). Volume and long runs decide.
- **Short timeline**: under about 8 weeks to a half or a marathon with a long run below half the race distance, say it plainly and offer a finish-focused plan or a later race.

## Step 7 - Design the plan

### Calendar and phases

Weeks run Monday to Sunday and the race week is the last one; `check --start --race` prints the dates. Week 1 is the week in progress, starting today, unless the runner says otherwise. Straight after a race, recover before building: 3-7 easy days after a 5K or 10K, 1-2 easy weeks after a half, 2-4 weeks after a marathon with the first one very light (convention).

Rough proportions: **Base** 30-40% (frequency and volume, strides, at most one light quality session), **Build** 35-45% (quality sessions and a growing long run), **Specific** 15-20% (race-pace work, the longest runs), then **Taper**. With under 8 weeks, drop the story: keep the routine, add race-specific work, taper. With no race, work in blocks of 4-6 weeks toward a volume or long-run target, each ending with a lighter week and a small test.

Starting from little or nothing: three run-walk sessions a week (for example 1 min running, 1-2 min walking, for 20-30 min), lengthening the running segments before anything else, with no pace targets.

### The week

| Runs/week | Skeleton |
|---|---|
| 2 | Long run + one run alternating easy and quality. Say honestly that two a week maintains; three builds. |
| 3 | Long + quality + easy. |
| 4 | Long + quality + two easy, strides after one. |
| 5 | Long + two quality (or one quality and one medium-long) + two easy. |
| 6-7 | Long + two quality + easy and recovery runs. |

- Keep an easy or rest day between hard days. The long run is a hard day when it contains pace work or sits near its ceiling.
- Most sessions are easy (about four in five). Hard running, threshold pace and faster, usually totals 10-20% of weekly running time; beyond that, more easy running is the better investment.
- Newer runners, anyone with a niggle, anyone returning: strides or hills first, structured sessions after 4-6 steady weeks. After an injury, choose what spares the injured area (no hills or sprints on a recovering calf or Achilles).
- Adding a day: add it as a short easy run and hold weekly volume roughly level for a week or two.
- Put sessions on the runner's usual days. If they lift, keep heavy leg work away from the day before a key run.
- Recovery slows with age for many runners: ask how they bounce back and add an easy day after hard ones if needed.

### Progression

- **Long run**: no run more than 10% longer than the longest of the previous 30 days (at least 1 km of headroom at short distances). This is the best running-specific evidence available. Cap by time too: about 3 h in marathon training, 2 h to 2 h 15 for a half, 90 min for a 10K, 75 min for a 5K (convention). Slower runners reach the time cap before the textbook distance: the time cap wins, and that is fine; tell them. Typical peaks: marathon 28-32 km, half 16-20 km, 10K 12-16 km, 5K 8-12 km.
- **Weekly volume**: about 5-10% over the recent peak in build weeks; at low volume think in absolute steps (one short run, 3-5 km). Avoid weeks more than about 30% above the recent 4-week average. Coming back to a volume held in the last few weeks is not a spike.
- **Lighter week** every third to fifth week: 15-30% less, same frequency, a touch of intensity. It is a convention for absorbing load, so if life already delivered an easy week, count it. Low-volume runners can go 4-5 weeks between them; high-load or slower-recovering runners 2-3.
- **One big change at a time** where you can: add a day, or lengthen, or intensify.
- **After a break**: up to a week off, resume; 1-2 weeks, about 75% of previous volume; 2-4 weeks, 50-60% and no hard session in the first week; longer, rebuild from short easy runs, adding at most one short run or 3-4 km a week (run-walk after an injury), and keep any cross-training going to carry the aerobic load. After illness with fever, wait until symptom-free, then a few easy days (convention).
- **No ACWR.** Do not compute or display an acute:chronic workload ratio; see the evidence section.

### Paces

Take them from `paces`. Give each as a range with an effort cue, and let effort win when they disagree (heat above roughly 20-25 °C, humidity, hills, trail, tired legs).

- **Easy**: conversational. The fast end of the range is a ceiling; there is no floor.
- **Marathon and half-marathon pace**: the equivalents line gives them at current fitness. Use goal pace only once a checkpoint shows fitness has moved.
- **Threshold**: comfortably hard, roughly what could be raced for an hour. 15-40 min in total per session.
- **Interval**: hard, reps of 2-5 min, 10-24 min of hard running in total, jog recoveries about as long as the reps or a little shorter.
- **Reps and strides**: fast and relaxed, full recovery.

Hilly or trail goal: plan long runs by time, build weekly elevation toward the race's profile, and compare paces only on similar terrain.

### Session menu

Each quality session starts with 10-15 min easy and ends with 5-10 min easy, all counted in weekly volume. Progress one thing at a time: reps, then duration, then pace.

- **Strides**: 4-8 x 15-20 s smooth accelerations after an easy run, walk back.
- **Hills**: 6-10 x 45-60 s uphill, strong but controlled, jog down.
- **Fartlek** (a bridge for newer runners): 6-10 x 1 min brisk, 1-2 min easy.
- **Threshold**: 3 x 8 min (2 min jog), then 4 x 8, 2 x 15, 20-30 min continuous.
- **Intervals**: 5 x 3 min, then 6 x 800 m, 5 x 1000 m, 4 x 4 min.
- **Race pace, half**: long run with the last 3-5 km at half pace, then 2 x 4 km, then 8-10 km at half pace inside a long run.
- **Race pace, marathon**: 8, then 12, then 16 km (5, 7, 10 mi) at marathon pace inside long runs, never more than about half the run, every second or third week.
- **Race pace, 5K and 10K**: in the last 4-5 weeks, 5-6 x 1 km at 10K pace or 6-8 x 400-600 m at 5K pace.

### Taper

About two weeks, volume down progressively by 40-60%, frequency and intensity kept (short touches at race pace). Marathon: 2-3 weeks, last long run 2-3 weeks out. Half: 7-14 days. 5K and 10K: 5-10 days.

### Around the running

- **Strength.** If Strava shows they already lift, coordinate; otherwise suggest two short sessions a week of loaded basics (squat or lunge, hinge, calf raises, hops when ready). Say what is true: trials show it improves running economy; that it prevents running injuries is unproven.
- **Fuelling.** For runs beyond about 75-90 min and for racing a half or a marathon, practise taking carbohydrate in long runs (commonly 30-60 g per hour, more for a marathon with practice) and the race-morning breakfast. General guidance, not a nutrition plan.
- **Life.** A week of bad sleep or heavy stress is a reason to swap a hard session for an easy run.

## Step 8 - Lint, then deliver

Draft one row per week, `week,volume,long,type`, and lint it against the real recent weeks. Types: `build`, `down` (any lighter, recovery or tune-up week), `taper`, `race`. In the race-week row give only the runs planned before the race, and the longest of them.

```bash
python3 runcoach.py check --recent 29,33,31,34 --recent-long 16.5 --start 2026-06-01 --race 2026-09-13 [--unit mi] <<'EOF'
1,32,17,build
2,34,18,build
3,27,13,down
# ...one row per week, down to the race week
EOF
```

`--recent` takes the last complete weeks, oldest first; `--recent-long` the longest run of the last 30 days, with `--recent-long-date` when that run is more than a week old. Fix every SPIKE and long-run ceiling note, weigh each "review", and re-run until what remains is a choice you can explain to the runner.

Deliver in the runner's language and units, as a document or artifact when the environment has one and in the conversation otherwise:

1. **Where you are**: the Strava picture in a few lines, estimates marked, and the assumptions you made if nobody could answer.
2. **The goal and what it takes**: the reality check, A and B goals, the checkpoint.
3. **Your paces**: a small table of ranges with effort cues.
4. **The plan at a glance**: one row per week with dates, phase, volume, long run and key sessions. Name the quality session and any pace work inside the long run, so a later check-in knows what was planned.
5. **The next 2-4 weeks in detail**: day by day on their usual days, and for each session what, how long, how hard, and why in a phrase. Say which sessions can move and which must stay apart. Later weeks are detailed at check-ins because they will be adjusted to what actually happens; detail everything now if the runner asks.
6. **Race week and race day** (when there is a race): what to run that week, the target pace judged by the course's kilometre or mile markers and not the watch, an opening a little slower than target, fuelling as rehearsed, and what to give up if it is hot.
7. **How to adapt**: a missed run, a bad week, the pain rule, heat.
8. **Check-ins**: invite them back every week or two, and after any race.

```
| Wk | Dates        | Phase | Volume | Long run | Key session                 |
| 1  | 1-7 June     | Base  | 32 km  | 17 km    | 8 x 20 s strides            |
| 2  | 8-14 June    | Base  | 34 km  | 18 km    | 3 x 8 min threshold         |
```

Keep it tight. Explain a term only when the runner is new to it.

## Check-in mode

1. **Find the plan**: earlier in the conversation, pasted, or in a file. Without one, do a read-out.
2. **Pull**: call 3 over at least the last 8 weeks, then `digest`, plus detail calls for the key sessions of the period (`activity --laps` shows how a session was run).
3. **Planned vs done**: sessions, volume, long run, and how the key session went (rep paces against targets, HR at a given pace against earlier weeks).
4. **Read it.** About 80% or more of the plan done, sessions on target: carry on. Signs of strain: easy runs slower at the same or higher HR for two weeks or more, two key sessions missed or cut short, relative effort climbing while volume does not, or the runner reports fatigue, poor sleep or a niggle. Signs of headroom: key sessions clearly comfortable, lower HR at the same paces.
5. **Adjust the next 1-2 weeks**, then re-run `check` with the actual recent weeks:
   - Missed easy run: gone. Missed key session: move it if hard days stay apart, otherwise drop it. Never stack sessions to catch up.
   - About a week missed: restart at about the level of the last completed week and move each remaining build week down one row of the plan. Protect the taper and the race-specific weeks; give up the least specific session instead. Two or more: apply the after-a-break rules and rebuild; if the race is close, shrink the goal, not the recovery.
   - After illness: judge the first run back against a normal easy run. Slower at a higher heart rate means not recovered yet, so the week stays easy.
   - Ahead of plan: do not speed up the volume build. Raise paces only on evidence (a race, a time trial, or two key sessions that were clearly too easy) and at most every 4-6 weeks.
   - Strain: cut volume 20-30% for a week and make the hard session easy.
   - Pain: apply the pain rule.
6. **Reply short**, in this order: the decision in one sentence; planned versus done in two or three lines with numbers; this week's sessions; what changes later, showing at-a-glance rows only for the weeks that change; what would change the call. Aim for 150-300 words plus that table. Leave out a fresh goal analysis unless the check-in changes the goal, and anything the runner already knows.

## Activity feedback mode

One run, read against this runner's own recent running. It is not a training read-out: do not pull twelve weeks for it, and do not turn the answer into a plan.

1. **Find the run and its frame.** Run together: `get_athlete_profile` and `get_athlete_zones` (unless the conversation already has them), and `search_activities` with run types, `start_date_min` = 6 weeks ago, `include_tags: true`, `first: 60`. That one list locates the run (the latest by default; otherwise match the day, name or distance they gave, and say which run you took), carries its weather and the runner's notes, and is the comparison set: recent runs of the same kind, the longest run of the 30 days before it, what was run in the two days before. A short run on the same day is its warm-up or cool-down. Give the run a `kind` as in step 2. When a plan is in the conversation, the planned session is the reference. For an `other`, a treadmill run or a manual entry, say what cannot be judged and keep to the summary.
2. **Pull the detail**, each call for a reason:
   - `get_activity_performance` on the run: average and max HR (check `has_heartrate`), laps, best efforts.
   - `get_activity_streams` on the run: `["time","distance","heart_rate","altitude"]`, `resolution` about 8 points per km (100 up to 12 km, 200 up to 25 km, 300 beyond). Skip it for a workout whose laps mirror the session.
   - `get_activity_performance` on one or two recent runs of the same kind, when their heart rate would settle the verdict.
   - A workout or a race is judged against the runner's current paces. If the conversation does not have them, make calls 6 and 7 of step 1 and run `paces`, leaving out the race being judged: what matters is what fitness supported before it.
3. **Run the numbers.** Pipe the streams to the script exactly as the connector returned them; give laps on the command line:

```bash
python3 runcoach.py activity --kind long --zones 121,151,166,180 --prior-longest 16200 [--unit mi] <<'EOF'
{"heart_rate":[131,138,...],"distance":[0,106.1,...],"altitude":[12.4,...],"time":[0,37,...]}
EOF
python3 runcoach.py activity --kind workout --target 4:20-4:27 \
  --laps 2000:720:135 1000:245:171 400:150:145 1000:248:174 400:155:149 1000:257:176 1500:570:150 < /dev/null
```

   `--kind` is `easy`, `long`, `workout` or `race`. `--zones` takes the `max` of heart-rate zones 1 to 4. `--prior-longest` is the longest run of the 30 days before this one, in metres. `--laps` lists every lap in order as `distance:moving_time:avg_hr`; the script guesses which laps are the repetitions and says so, and `--reps 2,4,6` corrects it. `--target` is the pace range the reps were meant for, from `paces` or the plan. Output: splits per km or mile, quarters and halves, steadiness, stops, drift (easy and long runs), time in zones, and the reps with their spread, trend and recoveries. Stream time is elapsed time, so a stop shows up as a slow split. That is the honest pace, and it differs from Strava's moving-time average.
4. **Read it by kind**, against the runner's own recent runs of that kind before any table.
   - **Easy run.** One question: was it easy? Heart rate decides, as in step 4: zones 1-2 when the zones are believable, or at or below their usual easy-run HR. Pace is not a result here. Faster than usual at the usual heart rate is a good sign, not a reason to speed up.
   - **Long run.** Length first: a run over the 10% line is the finding that matters, whatever the pace was, and the next long run goes back to the level before it instead of building on it. Then the shape: even, or a faster finish, is a good long run; a fade points to a start faster than their usual long-run pace, heat, no fuel, or a distance not trained yet, and usually to more than one. Then drift: heart rate creeping up at a steady pace is normal and grows with heat; a large fall in speed per heartbeat (over about 5%, by convention) on a cool day at a steady pace says the duration is at the edge of current endurance. Stops and hills distort it.
   - **Workout.** Reps against the target range: how many in range, the spread, the trend. Read rep by rep, because a mean pace on target can hide a session run badly. Fast first reps and slow last ones mean the session became a different session, and lengthening recoveries tell the same story. Even reps with the last one fastest is a session well run. When the reps missed, check the target against `paces` before blaming the runner: the target may be the error. Heart rate lags by a minute or more, so never judge a short rep or a first rep by it. With one lap or auto-laps, streams at this resolution cannot resolve short reps: say so, and judge the whole or ask for the structure.
   - **Race.** The result first, from the official time and distance (step 2), against the equivalent `paces` gave from earlier results. Then the pacing: halves within about 2% are even; an opening well under the average followed by a fade is a pacing error, and the comparison that shows it is the first km or mile against the pace fitness supported, not against the goal. A badly paced race understates fitness, so keep the earlier anchor when it is higher and fresher than 12 weeks, and say why. A well-paced race is the new anchor: offer updated paces. Then recovery, by the calendar rule in step 7.
   - **Always**: temperature and humidity against their usual, the climb column (a slow split with 15 m of climb is not a slow split), and the two days before.
5. **Know what the data cannot carry.** Wrist heart rate can read high in the opening minutes or stick at a flat value: trust the pattern, not a point, and say so when the script flags it. One odd split is GPS noise. Without heart rate, read the pacing only and say so. Do not comment on cadence, stride or form from watch data. One training run is not a fitness test: say what the run shows, not what kind of runner they are.
6. **Reply short**, in this order: the verdict in one sentence; the three or four numbers that carry it, with a few splits or reps in a small table only when the shape is the point; what explains it, separating what the data shows from what you suspect; what to do in the next days and in the next run of this kind; at most one question, and only if the answer would change the reading (how it felt, what was eaten or drunk). Aim for 120-250 words plus the table. If a plan is in the conversation and this run changes the coming days, say how.

## What the evidence supports

- **Reasonably supported.** Sudden jumps in a single run raise overuse-injury risk: in a 2025 cohort of 5,205 runners, runs more than 10% longer than the longest of the previous 30 days carried roughly 1.5 to 2.3 times the injury rate. A previous injury is the most consistent predictor of the next one. Newer runners are injured more often per hour than established ones. Mostly-easy training with a small dose of hard work. A taper of about two weeks that cuts volume by 41-60% and keeps intensity. Strength training improves running economy. Late collapses are common in recreational marathons: in more than four million race records, 28% of men and 17% of women hit the wall. In 82,303 recreational marathoners, those whose heart rate rose least against their speed late in the race ran faster for their fitness (weather was not accounted for).
- **Convention: use it, don't oversell it.** The 10% weekly rule (a trial in novices found no benefit over a faster build; jumps above about 30% are the concern). Lighter weeks. One change at a time. The return-from-break percentages. Long-run time caps. Phase proportions. The goal-gap rule of thumb. The thresholds for reading one run: 5% of drift, 2% between halves, the fast-start and fade notes the script prints.
- **Not supported: avoid.** The ACWR "sweet spot" of 0.8-1.3 and any injury-risk percentage attached to it: it comes from team sports, and in that same runner cohort neither ACWR nor week-to-week change predicted injury the way the model claims. "Strength training cuts running injuries by X%": pooled trials in runners show no clear effect, except in supervised programmes. Claims that polarized beats pyramidal training or the reverse: differences are small and individual. Age-based maximum heart rate formulas treated as fact. A fitness verdict from one training run.

## Safety

- **Pain rule.** Running is fine when pain stays at or under 3/10, does not build during the run, is gone the next day and does not change the stride. Otherwise switch to easy running or cross-training. Pain that alters the stride, sharp or pinpoint bone pain, swelling, pain at rest or at night, or anything lasting more than a week or two: stop and see a physiotherapist or sports doctor. Do not diagnose or prescribe rehabilitation.
- Chest pain, fainting, unusual breathlessness or palpitations: stop and get medical advice. Someone starting from inactivity with known heart or metabolic disease needs a medical go-ahead first.
- Never comment on weight or suggest weight loss; Strava's profile includes weight, so ignore it. Signs of under-fuelling (missed periods, repeated stress fractures, lasting exhaustion) call for a clinician, not a training change.
- Under-18s, pregnancy and the months after birth: encourage, keep advice general, and point to professional guidance.

## Without Strava

Work from what the runner tells you or pastes (a screenshot of recent weeks is enough): runs per week, weekly volume, longest recent run, a recent race or time trial, how long they have been running. The same steps apply, but treat the numbers as soft: start at the low end of what they report, mark the plan provisional, and offer to redo it once Strava is connected.

## Without code execution

Do less, and say the figures are approximate. Add up the last 6 complete weeks by hand (sessions, volume, longest run) and skip the finer flags. Take paces from the closest row below, using the runner's best recent result at any of the four distances:

| 5K | 10K | Half | Marathon | Easy /km | Threshold /km | Interval /km |
|---|---|---|---|---|---|---|
| 18:00 | 37:20 | 1:22:33 | 2:52:25 | 4:39-5:08 | 3:52 | 3:33 |
| 20:00 | 41:28 | 1:31:50 | 3:11:17 | 5:08-5:39 | 4:16 | 3:56 |
| 22:30 | 46:40 | 1:43:27 | 3:34:43 | 5:44-6:19 | 4:46 | 4:23 |
| 25:00 | 51:53 | 1:55:04 | 3:57:55 | 6:19-6:57 | 5:16 | 4:51 |
| 27:30 | 57:08 | 2:06:38 | 4:20:54 | 6:55-7:36 | 5:46 | 5:19 |
| 30:00 | 1:02:23 | 2:18:10 | 4:43:39 | 7:30-8:13 | 6:16 | 5:47 |
| 33:00 | 1:08:41 | 2:31:53 | 5:10:40 | 8:11-8:58 | 6:52 | 6:20 |
| 36:00 | 1:14:59 | 2:45:30 | 5:37:22 | 8:52-9:41 | 7:27 | 6:53 |
| 40:00 | 1:23:22 | 3:03:27 | 6:12:33 | 9:45-10:39 | 8:14 | 7:37 |

Per mile, multiply by 1.609. When you draft the plan, apply the progression rules by hand to every week.

For feedback on one run, work from the summary and the laps: average pace and heart rate against recent runs of the same kind, rep paces from the laps, and the two halves of a race from its best efforts when they exist. Leave drift and time in zones out.

## The script

```python
# runcoach.py - the arithmetic for the Strava running coach skill (Python 3.9+, stdlib only).
#   digest : weekly load picture from a run list     paces    : fitness anchor -> training paces, goal check
#   check  : lint a drafted plan                      activity : one run from its streams and laps
#   (each subcommand has -h)
import argparse, bisect, json, math, statistics as st, sys
from datetime import date, timedelta

KM = {"mile": 1.609344, "5k": 5.0, "10k": 10.0, "hm": 21.0975, "m": 42.195}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def secs(s):
    p = [float(x) for x in str(s).split(":")]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p)))

def hms(s):
    s = int(round(s)); h, m = divmod(s // 60, 60)
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"

def hm(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}"

def dist_km(d):
    return KM.get(d.lower()) or float(d)

# ---- Daniels & Gilbert oxygen-cost / duration model (the maths behind "VDOT") ------------------
def vo2(v):                      # oxygen cost of running at v m/min
    return -4.60 + 0.182258 * v + 0.000104 * v * v

def sustainable(t):              # fraction of VO2max that can be held for t minutes
    return 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)

def vdot(km, s):
    return vo2(km * 1000 / (s / 60)) / sustainable(s / 60)

def speed(cost):                 # m/min at a given oxygen cost
    return (-0.182258 + math.sqrt(0.182258 ** 2 + 4 * 0.000104 * (cost + 4.60))) / 0.000208

def equiv(vd, km):               # seconds to cover km at a given VDOT (bisection)
    lo, hi = km * 100, km * 1200
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if vdot(km, mid) > vd else (lo, mid)
    return lo

def cmd_paces(a):
    per, lab = (1.609344, "/mi") if a.unit == "mi" else (1.0, "/km")
    pace = lambda mpm: hms(60000 / mpm * per)
    today, res = date.fromisoformat(a.today), []
    for r in a.result:               # dist,time[,date[,label]]
        f = [x.strip() for x in r.split(",", 3)]
        km, s = dist_km(f[0]), secs(f[1])
        age = (today - date.fromisoformat(f[2])).days / 7 if len(f) > 2 and f[2] else None
        res.append((vdot(km, s), f[0], hms(s), age, f[3] if len(f) > 3 else ""))
    print("RESULTS")
    for v, d, t, age, note in res:
        print(f"  {d:>5} {t:>8}  VDOT {v:4.1f}  {'' if age is None else f'{age:.0f} wk ago':>9}  {note}")
    fresh = [r for r in res if r[3] is None or r[3] <= a.fresh]
    v, d, t, _, _ = max(fresh or res, key=lambda r: r[0])
    print(f"ANCHOR  VDOT {v:.1f} from {d} {t}" + ("" if fresh else
          f"  (nothing within {a.fresh} weeks: stale, treat every pace as provisional)"))
    if a.layoff > 5:                 # Daniels' return-from-break table: ~0.3% a day after day 5, 20% at most
        loss = min(0.2, 0.003 * (a.layoff - 5)) * (0.5 if a.cross_trained else 1)
        print(f"LAYOFF  {a.layoff} d without running since the anchor{', cross-trained' if a.cross_trained else ''}:"
              f" VDOT {v:.1f} -> {v * (1 - loss):.1f} (rule of thumb; everything below is provisional until a test)")
        v *= 1 - loss
    print("EQUIVALENTS at this VDOT (optimistic for distances longer than the anchor unless the endurance is trained)")
    print("  " + " | ".join(f"{k} {hms(equiv(v, KM[k]))} ({hms(equiv(v, KM[k]) / KM[k] * per)}{lab})"
                            for k in ("5k", "10k", "hm", "m")))
    i = speed(0.975 * v)
    rng = lambda mpm: f"{pace(mpm * 1.012)}-{pace(mpm * 0.988)}"
    print(f"TRAINING PACES ({lab})")
    print(f"  easy {pace(speed(0.70 * v))}-{pace(speed(0.62 * v))} (fast end is a ceiling, slower is fine)"
          f" | threshold {rng(speed(0.88 * v))} | interval {rng(i)} | reps about {hms((60000 / i - 15) * per)}")
    if a.goal:
        gd, gt = [x.strip() for x in a.goal.split(",")[:2]]
        gs, cur = secs(gt), equiv(v, dist_km(gd))
        gap = (cur - gs) / cur * 100
        budget = 0.25 * min(a.weeks, 20) if a.weeks else 3.0
        verdict = ("already there" if gap <= 0 else "realistic" if gap <= budget else
                   "stretch" if gap <= 2 * budget else "long shot this cycle")
        if min(abs(gap), abs(gap - budget), abs(gap - 2 * budget)) < 0.5:
            verdict += " (borderline: within half a point of the next verdict)"
        print(f"GOAL  {gd} {hms(gs)} ({hms(gs / dist_km(gd) * per)}{lab}) = VDOT {vdot(dist_km(gd), gs):.1f};"
              f" current equivalent {hms(cur)}; gap {gap:.1f}% -> {verdict}"
              f" (rule of thumb ~0.25%/week of consistent training"
              f"{f', {a.weeks} wk available' if a.weeks else ''}; newer runners often beat it)")

def cmd_digest(a):
    U, per = ("mi", 1.609344) if a.unit == "mi" else ("km", 1.0)
    today, since = date.fromisoformat(a.today), date.fromisoformat(a.since)
    mon = lambda d: d - timedelta(days=d.weekday())
    first = mon(since) if since == mon(since) else mon(since) + timedelta(days=7)
    rows = []
    for line in sys.stdin:           # start_local,distance,moving_time,elapsed_time,elevation_gain,relative_effort,kind
        f = [x.strip() for x in line.split(",")]
        if len(f) < 3 or not f[0][:4].isdigit():
            continue
        f += [""] * (7 - len(f))
        try:
            day, _, clock = f[0].replace(" ", "T").partition("T")
            hh = (clock or "0:0").split(":")
            r = dict(d=date.fromisoformat(day), t0=int(hh[0]) * 3600 + int(hh[1]) * 60, km=float(f[1]) / 1000,
                     mov=float(f[2]), ela=float(f[3] or f[2]), elev=float(f[4] or 0),
                     re=float(f[5]) if f[5] else None, kind=(f[6] or "easy").lower())
        except (ValueError, IndexError):
            sys.exit(f"bad row: {line.strip()!r}\nexpected start_local,distance,moving_time,elapsed_time,"
                     "elevation_gain,relative_effort,kind (raw Strava SI values)")
        if first <= r["d"] <= today:
            rows.append(r)
    rows.sort(key=lambda r: (r["d"], r["t0"]))
    runs, dup = [], 0
    for r in rows:                   # same outing uploaded twice -> keep the richer record
        p = runs[-1] if runs else None
        if p and p["d"] == r["d"] and r["t0"] <= p["t0"] + p["ela"]:
            dup += 1
            if (r["re"] is not None, r["km"]) > (p["re"] is not None, p["km"]):
                runs[-1] = r
        else:
            runs.append(r)
    race_days = {r["d"] for r in runs if r["kind"] == "race"}
    for r in runs:                   # volume only: tiny runs, race-day warm-ups and cool-downs, non-running "other"
        r["micro"] = (r["mov"] < 600 or r["km"] < 1.5 or r["kind"] == "other"
                      or (r["d"] in race_days and r["kind"] != "race" and r["mov"] < 1500))
    sess = [r for r in runs if not r["micro"]]
    agg, w = [], first
    while w <= today:
        rs = [r for r in runs if mon(r["d"]) == w]
        ss = [r for r in rs if not r["micro"]]
        agg.append(dict(w=w, n=len(ss), days=len({r["d"] for r in ss}), km=sum(r["km"] for r in rs),
                        s=sum(r["mov"] for r in rs), elev=sum(r["elev"] for r in rs),
                        long=max(ss, key=lambda r: r["km"]) if ss else None,
                        hard=sum(r["kind"] in ("workout", "race") for r in ss),
                        re=sum(r["re"] or 0 for r in rs), race=any(r["kind"] == "race" for r in rs),
                        partial=w + timedelta(days=6) >= today))
        w += timedelta(days=7)
    print(f"WEEKS (Mon-start, {U}; * = in progress)")
    print("week of     sess days   dist  h:mm elev(m) longest hard   RE")
    for g in agg:
        print(f"{g['w']}{'*' if g['partial'] else ' '} {g['n']:4d} {g['days']:4d} {g['km'] / per:6.1f} {hm(g['s']):>5}"
              f" {g['elev']:5.0f} {g['long']['km'] / per if g['long'] else 0:8.1f} {g['hard']:4d} {g['re']:4.0f}"
              f"{'  race' if g['race'] else ''}")
    full = [g for g in agg if not g["partial"]]
    if not full or not sess:
        print("Not enough data for a summary."); return
    kms = [g["km"] for g in full]
    blocks = [(st.mean(kms[i - 3:i + 1]), full[i]["w"]) for i in range(3, len(kms))]
    cnt = [g["n"] for g in full[-8:]]
    print("SUMMARY")
    print(f"  complete weeks {len(full)} | weeks with a run {sum(g['n'] > 0 for g in full)}"
          f" | sessions/wk median {st.median(cnt):g} (range {min(cnt)}-{max(cnt)}, last 8)")
    line = (f"  volume/wk: last-4 avg {st.mean(kms[-4:]) / per:.1f} {U} ({hm(st.mean(g['s'] for g in full[-4:]))})"
            f" | median last 8 {st.median(kms[-8:]) / per:.1f}")
    if blocks and max(blocks)[0] > 0:
        b = max(blocks)
        line += f" | best 4-wk block {b[0] / per:.1f} (weeks of {b[1] - timedelta(days=21)} to {b[1]})"
    print(line)
    ds = sorted({r["d"] for r in sess})
    gap = max([(y - x).days - 1 for x, y in zip(ds, ds[1:])] + [(ds[0] - first).days])
    print(f"  days since last run {(today - ds[-1]).days} | longest gap without a run {gap} d")
    recent = [r for r in sess if r["d"] > today - timedelta(days=56)]
    gaps = [(x, y) for x, y in zip(ds, ds[1:]) if (y - x).days > 14]
    if gaps and gaps[-1][1] > today - timedelta(days=56):
        x, y = gaps[-1]
        print(f"  BREAK: no run from {x + timedelta(days=1)} to {y - timedelta(days=1)} ({(y - x).days - 1} d);"
              f" the rhythm and pace lines below use only the runs since {y}")
        recent = [r for r in sess if r["d"] >= y]
        before = [g for g in full if g["w"] + timedelta(days=6) <= x and g["n"]][-6:]
        if before:
            days = [r["d"].weekday() for r in sess if before[0]["w"] <= r["d"] <= x]
            print(f"  before the break ({len(before)} wk): {st.mean(g['km'] for g in before) / per:.1f} {U}/wk,"
                  f" {st.median(g['n'] for g in before):g} sessions/wk,"
                  f" usual days {' '.join(DOW[i] for i in range(7) if days.count(i) >= len(before) / 2)},"
                  f" longest run {max(g['long']['km'] for g in before) / per:.1f} {U}")
    need = min(4, max(2, len({mon(r["d"]) for r in recent}) // 2))
    usual = [DOW[i] for i in range(7) if sum(r["d"].weekday() == i for r in recent) >= need]
    longs = [g["long"] for g in full[-8:] if g["long"]]
    print(f"  usual run days ({need}+ times in the period): {' '.join(usual) or 'no fixed pattern'}"
          + (f" | longest run usually on {DOW[st.mode([r['d'].weekday() for r in longs])]}" if longs else ""))
    in30 = [r for r in sess if r["d"] >= today - timedelta(days=30)]
    if in30:
        top = max(in30, key=lambda r: r["km"])
        line = (f"  longest run, last 30 d: {top['km'] / per:.1f} {U} in {hm(top['mov'])} on {top['d']}"
                f" ({top['kind']}) -> ceiling for the next long run {max(top['km'] * 1.1, top['km'] + 1) / per:.1f} {U}")
        nr = [r for r in in30 if r["kind"] not in ("race", "other")]
        if nr and max(nr, key=lambda r: r["km"]) is not top:
            t2 = max(nr, key=lambda r: r["km"])
            line += f" | longest training run {t2['km'] / per:.1f} on {t2['d']}"
        print(line)
    else:
        print("  no run in the last 30 days -> treat as a return from a break")
    share = [g["long"]["km"] / g["km"] for g in full[-6:] if g["long"] and g["km"]]
    if share:
        print(f"  weekly longest run (last 6): median {st.median(g['long']['km'] for g in full[-6:] if g['long']) / per:.1f}"
              f" {U} = {st.median(share) * 100:.0f}% of the week")
    easy = [r["mov"] / r["km"] for r in recent if r["kind"] in ("easy", "long") and r["mov"] >= 1200]
    if easy:
        print(f"  typical easy pace (median of {len(easy)} easy/long runs, moving time): {hms(st.median(easy) * per)}/{U}")
    print(f"  hard sessions/wk (last 6): {st.mean(g['hard'] for g in full[-6:]):.1f}")
    cov = sum(r["re"] is not None for r in sess) / len(sess)
    if cov >= 0.7 and len(full) >= 5 and full[-1]["re"]:
        print(f"  relative effort: last week {full[-1]['re']:.0f} vs prior 4-wk avg "
              f"{st.mean(g['re'] for g in full[-5:-1]):.0f} (present on {cov * 100:.0f}% of runs)")
    print("FLAGS")
    for i in range(4, len(full)):
        base = st.mean(kms[i - 4:i])
        if base >= 8 and kms[i] > 1.3 * base and kms[i] > 1.05 * max(kms[max(0, i - 5):i]):
            print(f"  week of {full[i]['w']}: {kms[i] / per:.1f} {U} = +{(kms[i] / base - 1) * 100:.0f}% vs prior 4-wk avg")
    for r in sess:
        prior = [p["km"] for p in sess if r["d"] - timedelta(days=30) <= p["d"] < r["d"]]
        if (r["d"] >= first + timedelta(days=30) and prior and r["km"] > max(1.1 * max(prior), max(prior) + 1)
                and r["kind"] != "race"):
            print(f"  {r['d']}: {r['km'] / per:.1f} {U} run was +{(r['km'] / max(prior) - 1) * 100:.0f}% over the"
                  f" longest of the prior 30 d ({max(prior) / per:.1f})")
    paused = sum(r["ela"] > 1.25 * r["mov"] or r["ela"] - r["mov"] > 600 for r in sess if r["kind"] in ("easy", "long", "workout"))
    for n, msg in ((dup, "duplicate upload(s) dropped"),
                   (sum(r["micro"] for r in runs), "activity(ies) counted in volume only (under 10 min, race-day warm-up, or 'other')"),
                   (paused, "run(s) with long pauses: moving-time pace flatters them")):
        if n:
            print(f"  {n} {msg}")

def cmd_check(a):
    U, tol, step = a.unit, (4 if a.unit == "km" else 2.5), (1 if a.unit == "km" else 0.6)
    hist = [float(x) for x in a.recent.split(",")]
    plan = []
    for line in sys.stdin:           # week,volume,long[,type]   type: build | down | taper | race (anything else = down)
        f = [x.strip() for x in line.split(",")]
        if len(f) >= 3 and f[0].isdigit():
            typ = (f[3] if len(f) > 3 and f[3] else "build").lower()
            plan.append((int(f[0]), float(f[1]), float(f[2]), typ if typ in ("build", "taper", "race") else "down"))
    start = date.fromisoformat(a.start) if a.start else None
    if start and start.weekday():
        print(f"warning: --start {start} is a {DOW[start.weekday()]}, weeks are meant to start on Monday")
    train = [p for p in plan if p[3] != "race"] or plan
    peak = max(p[1] for p in train) or 1
    vols, streak, shares, seed_rows = hist[:], 0, [], 4
    if start and a.recent_long_date:  # the recent long run only counts for rows within 30 days of it
        age = (start + timedelta(days=6) - date.fromisoformat(a.recent_long_date)).days
        seed_rows = max(0, min(4, (30 - age) // 7 + 1))
    print(f"wk  {'dates':<24} type   {U:>5}  vs-peak  long  share  notes")
    for n, (wk, v, lg, typ) in enumerate(plan):
        notes, top, avg = [], max(vols[-5:]), st.mean(vols[-4:])
        if typ in ("build", "down"):
            if top == 0:
                notes.append("no recent running: start with short easy runs or run-walk")
            elif v - vols[-1] > tol:     # a small absolute step is never a spike
                if v > 1.25 * top:
                    notes.append("SPIKE: >25% over the recent peak")
                elif v > 1.3 * avg and v > 1.05 * top:
                    notes.append("SPIKE: >30% over the 4-wk average")
                elif v > 1.12 * top:
                    notes.append("review: >12% over the recent peak")
            streak = streak + 1 if typ == "build" and v >= 0.9 * top else 0
            if streak == 5:
                notes.append("5th build week in a row: plan a lighter week")
        if typ != "race":
            prior = max([p[2] for p in plan[max(0, n - 4):n]] + ([a.recent_long] if n < seed_rows else []), default=0)
            ceil = max(1.1 * prior, prior + step)
            if prior and lg > ceil + 0.05:
                notes.append(f"long run over the ceiling ({ceil:.1f})")
            if v:
                shares.append(lg / v)
                if lg / v > 0.6:
                    notes.append("long run >60% of the week")
        else:
            prev = plan[n - 1][1] if n else hist[-1]
            notes.append(f"week before = {prev / peak * 100:.0f}% of peak, race week = {v / peak * 100:.0f}% (excl. race)")
            if prev > 0.85 * peak:
                notes.append("no visible taper")
        ds = f"{start + timedelta(days=7 * n)} to {start + timedelta(days=7 * n + 6)}" if start else ""
        vs = f"{(v / top - 1) * 100:+6.0f}%" if top else "    n/a"
        print(f"{wk:<3} {ds:<24} {typ:<6} {v:5.1f}  {vs}  {lg:4.1f}  {lg / v * 100 if v else 0:4.0f}%  {'; '.join(notes)}")
        vols.append(v)
    base = st.mean(hist[-4:])
    if base < 0.6 * max(hist) or min(hist[-4:]) == 0:   # a break, an illness or a taper: a percentage would mislead
        grow = f" (recent weeks are low; the earlier level was {max(hist):.1f})"
    else:
        grow = f" ({(peak / base - 1) * 100:+.0f}%)"
    print(f"last-4-week average {base:.1f} {U} -> peak {peak:.1f}{grow} over {len(plan)} weeks;"
          f" longest training run {max(p[2] for p in train):.1f} {U}")
    if shares and st.median(shares) > 0.5:
        print(f"long run is {st.median(shares) * 100:.0f}% of a typical week: a short extra easy run would spread the load better")
    if start and a.race:
        rd, last = date.fromisoformat(a.race), start + timedelta(days=7 * (len(plan) - 1))
        print(f"race {rd} ({DOW[rd.weekday()]}) " + ("is in the last plan week: OK" if last <= rd <= last + timedelta(days=6)
              else f"is NOT in the last plan week ({last} to {last + timedelta(days=6)}): fix the calendar"))

# ---- one activity: splits, pacing shape, heart-rate drift, stops, reps ---------------------------
def interp(xs, ys, x):               # linear interpolation of ys over non-decreasing xs
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_left(xs, x)
    return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1])

def tmean(t, ys, ta, tb):            # time-weighted mean of a stream between two times
    pts = [ta] + [x for x in t if ta < x < tb] + [tb]
    val = [interp(t, ys, x) for x in pts]
    return sum((pts[i + 1] - pts[i]) * (val[i] + val[i + 1]) / 2 for i in range(len(pts) - 1)) / (tb - ta) if tb > ta else val[0]

def read_streams(text):              # the connector's JSON as returned, or rows time,distance[,heart_rate[,altitude]]
    need = 'need the "time" and "distance" streams: request ["time","distance","heart_rate","altitude"] and pass the result unchanged'
    if text[0] in "{[":
        o = json.loads(text)
        while isinstance(o, dict) and "time" not in o and len(o) == 1:
            o = next(iter(o.values()))
        if isinstance(o, list):      # Strava's raw API shape: [{"type": "distance", "data": [...]}, ...]
            o = {s.get("type"): s for s in o if isinstance(s, dict)}
        if not isinstance(o, dict):
            sys.exit(need)
        o = {k: v.get("data") if isinstance(v, dict) else v for k, v in o.items()}
        cols = [o.get("time"), o.get("distance"), o.get("heart_rate") or o.get("heartrate"), o.get("altitude")]
    else:
        rows = [[x.strip() for x in ln.split(",")] for ln in text.splitlines() if ln.strip()[:1].isdigit()]
        cols = [[float(r[i]) if len(r) > i and r[i] else None for r in rows] for i in range(4)]
    t, d, hr, alt = cols
    if not t or not d or len(t) != len(d) or None in t or None in d:
        sys.exit(need)
    notes, n = [], len(t)
    if hr and len(hr) == n and sum(bool(h) for h in hr) >= 0.8 * n:
        if not all(hr):
            notes.append(f"heart rate missing on {sum(not h for h in hr)} of {n} samples: gaps filled from the neighbours")
        last = next(h for h in hr if h)
        for i, h in enumerate(hr):
            last = hr[i] = h or last
    else:
        if hr and any(hr):
            notes.append("heart rate stream too patchy to use")
        hr = None
    alt = alt if alt and len(alt) == n and None not in alt else None
    keep = [0]
    for i in range(1, n):            # time must move forward; distance never goes back
        if t[i] > t[keep[-1]]:
            keep.append(i)
    if len(keep) < 5:
        sys.exit("too few samples: ask for a higher resolution")
    pick = lambda xs: [xs[i] for i in keep] if xs else None
    t, d, hr, alt = pick(t), pick(d), pick(hr), pick(alt)
    t, d = [x - t[0] for x in t], [x - d[0] for x in d]
    for i in range(1, len(d)):
        d[i] = max(d[i], d[i - 1])
    if d[-1] <= 0:
        sys.exit("the distance stream never moves: nothing to analyse (treadmill without a footpod?)")
    return t, d, hr, alt, notes

def act_streams(a, text, per, lab):
    t, d, hr, alt, notes = read_streams(text)
    L, T, D = 1000 * per, t[-1], d[-1]
    pace = lambda m, s: hms(s / m * L) if m > 0 else "-"     # time per km or mile over m metres run in s seconds
    at = lambda x: interp(d, t, x)                           # elapsed time at a distance
    hrm = lambda x0, x1: tmean(t, hr, at(x0), at(x1))
    print(f"ACTIVITY  {D / L:.2f} {a.unit} in {hms(T)} = {pace(D, T)}{lab} on elapsed time"
          + (f" | HR avg {tmean(t, hr, 0, T):.0f}, max {max(hr):.0f}" if hr else " | no heart rate")
          + f" | {len(t)} samples, about {st.median(y - x for x, y in zip(d, d[1:])):.0f} m apart")
    vmed = st.median((y - x) / (v - u) for x, y, u, v in zip(d, d[1:], t, t[1:]))
    stops, cur = [], None            # [where it started (m), seconds lost against the usual speed]
    for i in range(1, len(t)):
        dt, dd = t[i] - t[i - 1], d[i] - d[i - 1]
        if dd / dt < 0.6 * vmed:
            cur = cur or [d[i - 1], 0.0]
            cur[1] += dt - dd / vmed
        elif cur:
            stops.append(cur)
            cur = None
    stops = [s for s in stops + ([cur] if cur else []) if s[1] >= 20]
    n = int(D // L)
    marks = [k * L for k in range(n + 1)] + ([D] if D - n * L >= 0.1 * L else [])
    print(f"SPLITS\n  {a.unit:>5} {'pace':>6}" + ("    HR" if hr else "") + ("  climb(m)" if alt else ""))
    full = []
    for k, (x0, x1) in enumerate(zip(marks, marks[1:]), 1):
        s, whole = at(x1) - at(x0), x1 - x0 > L - 1
        if whole:
            full.append((s, k))
        print(f"  {str(k) if whole else f'+{(x1 - x0) / L:.2f}':>5} {pace(x1 - x0, s):>6}"
              + (f"  {hrm(x0, x1):4.0f}" if hr else "") + (f"  {round(interp(d, alt, x1) - interp(d, alt, x0)):+8d}" if alt else "")
              + ("  stop or walk" if any(x0 <= p < x1 for p, _ in stops) else ""))
    if stops:
        print(f"STOPS  about {hms(sum(s for _, s in stops))} stopped or walking, at {a.unit} "
              + ", ".join(f"{p / L:.1f}" for p, _ in stops) + "; every pace here includes it")
    if len(full) >= 3:
        lo, hi = min(full), max(full)
        print(f"STEADINESS  fastest {a.unit} {lo[1]} ({hms(lo[0])}), slowest {a.unit} {hi[1]} ({hms(hi[0])}),"
              f" spread {(hi[0] - lo[0]) / st.median(s for s, _ in full) * 100:.0f}% of the median split")
    if a.kind != "workout" and D >= 3000:
        q = [D * i / 4 for i in range(5)]
        qs = [at(y) - at(x) for x, y in zip(q, q[1:])]
        print("QUARTERS  pace " + " | ".join(pace(D / 4, s) for s in qs)
              + ("   HR " + " | ".join(f"{hrm(x, y):.0f}" for x, y in zip(q, q[1:])) if hr else ""))
        h1, h2 = at(D / 2), T - at(D / 2)
        pct = (h2 / h1 - 1) * 100
        print(f"HALVES  first {pace(D / 2, h1)}{lab}, second {pace(D / 2, h2)}{lab}: {pct:+.1f}% = "
              + ("even" if abs(pct) < 2 else "positive split (slowed)" if pct > 0 else "negative split (sped up)")
              + (f" | HR {hrm(0, D / 2):.0f} -> {hrm(D / 2, D):.0f}" if hr else ""))
        last = (qs[3] / (D / 4)) / (h1 / (D / 2)) * 100 - 100
        if full and full[0][0] / L < 0.95 * T / D and len(full) >= 4:
            notes.append(f"fast start: first {a.unit} in {hms(full[0][0])} against {pace(D, T)} for the whole run")
        if last >= 4:
            notes.append(f"fade: last quarter {last:.1f}% slower than the first half")
        elif last <= -2:
            notes.append(f"strong finish: last quarter {-last:.1f}% faster than the first half")
    if a.kind in ("easy", "long") and hr and T >= 1800:
        mid, dist = (300 + T) / 2, lambda x: interp(t, d, x)
        v1, v2 = (dist(mid) - dist(300)) / (mid - 300), (D - dist(mid)) / (T - mid)
        b1, b2 = tmean(t, hr, 300, mid), tmean(t, hr, mid, T)
        drift = (1 - (v2 / b2) / (v1 / b1)) * 100
        print(f"DRIFT  second half against first, by time, first 5 min left out: pace {hms(L / v1)} -> {hms(L / v2)},"
              f" HR {b1:.0f} -> {b2:.0f}; speed per heartbeat {'down' if drift >= 0 else 'up'} {abs(drift):.1f}%"
              + (" (the stops distort this)" if sum(s for _, s in stops) > 0.02 * T else ""))
    if hr and a.zones:
        tops = [float(x) for x in a.zones.split(",")]
        share = [0.0] * (len(tops) + 1)
        for i in range(1, len(t)):
            share[bisect.bisect_left(tops, (hr[i] + hr[i - 1]) / 2)] += t[i] - t[i - 1]
        print("ZONES  " + " | ".join(f"Z{i + 1} {s / T * 100:.0f}%" for i, s in enumerate(share)) + f"  (share of time; zone tops {a.zones})")
    if a.prior_longest:
        ceil = max(1.1 * a.prior_longest, a.prior_longest + 1000)
        print(f"LENGTH  {D / L:.1f} {a.unit} against {a.prior_longest / L:.1f}, the longest run of the 30 days before:"
              f" {(D / a.prior_longest - 1) * 100:+.0f}% -> " + (f"over the 10% line ({ceil / L:.1f})" if D > ceil + 50 else "within the 10% line"))
    if hr and T >= 1200 and tmean(t, hr, 0, 0.08 * T) > tmean(t, hr, 0.08 * T, 0.25 * T) + 10:
        notes.append("heart rate starts high and then drops: probably a sensor error in the opening minutes")
    if hr and (max(hr) > 230 or min(hr) < 35):
        notes.append("implausible heart-rate values: check the sensor before reading HR")
    if st.median(y - x for x, y in zip(d, d[1:])) > L / 3:
        notes.append("samples are far apart for splits: ask for a higher resolution")
    for x in notes:
        print(f"NOTE  {x}")

def act_laps(a, per, lab):
    laps = []
    for item in a.laps:              # distance:moving_time[:avg_hr], raw Strava values
        f = item.strip(",").split(":")
        try:
            laps.append((float(f[0]), float(f[1]), float(f[2]) if len(f) > 2 and f[2] else None))
        except (ValueError, IndexError):
            sys.exit(f"bad lap {item!r}: expected distance:moving_time[:avg_hr], e.g. 1000:272:165")
    laps = [x for x in laps if x[0] > 0 and x[1] > 0]
    sp, pace = [m / s for m, s, _ in laps], lambda m, s: hms(s / m * 1000 * per)
    guessed = not a.reps
    if a.reps:
        work = sorted({int(x) - 1 for x in a.reps.split(",") if 0 < int(x) <= len(laps)})
    else:                            # warm-up and cool-down aside, split the laps at the biggest pace gap
        cand = sorted(range(len(laps))[1:-1] if len(laps) >= 4 else range(len(laps)), key=lambda i: sp[i])
        jump, k = max(((sp[cand[i + 1]] / sp[cand[i]], i) for i in range(len(cand) - 1)), default=(1, 0))
        work = cand[k + 1:] if jump >= 1.06 else []
        if work:                     # a first or last lap that looks like the reps is one of them
            md, mt, floor = st.median(laps[j][0] for j in work), st.median(laps[j][1] for j in work), 0.9 * min(sp[j] for j in work)
            like = lambda i: sp[i] >= floor and (abs(laps[i][0] / md - 1) <= 0.25 or abs(laps[i][1] / mt - 1) <= 0.25)
            work = sorted(set(work) | {i for i in (0, len(laps) - 1) if like(i)})
    print(f"LAPS  {len(laps)} laps" + ("" if work else ": no clear repetitions (auto-laps or a continuous run); name them with --reps if there are"))
    for i, (m, s, h) in enumerate(laps):
        print(f"  {i + 1:>3} {m:6.0f} m {hms(s):>6}  {pace(m, s):>5}{lab}" + (f"  HR {h:.0f}" if h else "") + ("  rep" if i in work else ""))
    if not work:
        return
    reps = [laps[i] for i in work]
    m, s = sum(r[0] for r in reps), sum(r[1] for r in reps)
    each = [r[1] / r[0] for r in reps]
    print(f"REPS  {len(reps)} (lap{'s' if len(reps) > 1 else ''} {', '.join(str(i + 1) for i in work)}" + ("; guessed from pace, correct with --reps" if guessed else "")
          + f"): {m / 1000 / per:.2f} {a.unit} in {hms(s)}, mean {pace(m, s)}{lab}")
    if len(reps) > 1:
        print(f"  fastest {hms(min(each) * 1000 * per)}, slowest {hms(max(each) * 1000 * per)}, spread {(max(each) / min(each) - 1) * 100:.1f}%"
              f" | last against first {(each[-1] / each[0] - 1) * 100:+.1f}%"
              + (f" | HR {reps[0][2]:.0f} -> {reps[-1][2]:.0f}" if all(r[2] for r in reps) else ""))
    rec = [laps[i][1] for i in range(work[0], work[-1]) if i not in work]
    if rec:
        print(f"  recoveries: {len(rec)}, mean {hms(st.mean(rec))} ({hms(min(rec))} to {hms(max(rec))})")
    if a.target:
        lo, hi = sorted(secs(x) for x in a.target.split("-"))
        fast = sum(p * 1000 * per < lo - 1 for p in each)
        slow = sum(p * 1000 * per > hi + 1 for p in each)
        print(f"  target {hms(lo)}-{hms(hi)}{lab}: {len(each) - fast - slow} in range, {fast} faster, {slow} slower")

def cmd_activity(a):
    per, lab = (1.609344, "/mi") if a.unit == "mi" else (1.0, "/km")
    text = "" if sys.stdin.isatty() else sys.stdin.read().strip()
    if not text and not a.laps:
        sys.exit("nothing to analyse: pipe the streams in, or give --laps")
    if text:
        act_streams(a, text, per, lab)
    if a.laps:
        act_laps(a, per, lab)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Arithmetic for the Strava running coach skill")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("digest", help="stdin: start_local,distance,moving_time,elapsed_time,elevation_gain,relative_effort,kind")
    p.add_argument("--since", required=True, help="start_date_min used for the Strava pull (YYYY-MM-DD)")
    p.set_defaults(fn=cmd_digest)
    q = sub.add_parser("paces", help="training paces and goal check from races / best efforts")
    q.add_argument("--result", action="append", required=True, help="dist,time[,date[,label]]  dist: 5k|10k|hm|m|mile|<km>")
    q.add_argument("--goal", help="dist,time")
    q.add_argument("--weeks", type=int, help="whole calendar weeks from today to race day (round down)")
    q.add_argument("--layoff", type=int, default=0, help="length in days of a break from running after the anchor result")
    q.add_argument("--cross-trained", action="store_true", help="aerobic cross-training was kept up during the layoff")
    q.add_argument("--fresh", type=int, default=12, help="oldest result (weeks) usable as anchor")
    q.set_defaults(fn=cmd_paces)
    c = sub.add_parser("check", help="stdin: week,volume,long[,type]")
    c.add_argument("--recent", required=True, help="actual weekly volumes, oldest first, e.g. 28,31,30,22")
    c.add_argument("--recent-long", type=float, required=True, help="longest run of the last 30 days")
    c.add_argument("--recent-long-date", help="date of that run, if it is more than a week old (needs --start)")
    c.add_argument("--start", help="Monday of plan week 1 (YYYY-MM-DD)")
    c.add_argument("--race", help="race date (YYYY-MM-DD)")
    c.set_defaults(fn=cmd_check)
    v = sub.add_parser("activity", help="stdin: the activity's streams as the connector returned them (JSON), or rows time,distance[,heart_rate[,altitude]]")
    v.add_argument("--kind", default="easy", choices=["easy", "long", "workout", "race"], help="what the run was meant to be")
    v.add_argument("--zones", help="tops of heart-rate zones 1-4 in bpm, e.g. 120,149,164,178")
    v.add_argument("--prior-longest", type=float, help="longest run of the 30 days before this one, in metres")
    v.add_argument("--laps", nargs="+", help="laps in order, each distance:moving_time[:avg_hr] (metres, seconds)")
    v.add_argument("--reps", help="lap numbers of the repetitions, e.g. 2,4,6 (guessed from pace when omitted)")
    v.add_argument("--target", help="target pace range for the repetitions in the runner's unit, e.g. 4:35-4:45")
    v.set_defaults(fn=cmd_activity)
    for s in (p, q, c, v):
        s.add_argument("--unit", default="km", choices=["km", "mi"])
        s.add_argument("--today", default=str(date.today()))
    a = ap.parse_args()
    a.fn(a)
```
