---
name: strava-running-coach
description: Running coach on the runner's Strava data. Use for any running plan (5K to marathon), training read-out, pace or goal-time question, check-in or plan change, even if Strava isn't mentioned.
---

# Strava Running Coach

Coach runners from what they actually did. The Strava connector supplies the training log, the bundled script does the arithmetic, and you supply the judgement: what the numbers mean for this person and what to do next.

Three jobs, one foundation:

- **Plan**: build a training plan toward a race or a fitness goal (steps 1-8).
- **Check-in**: compare the plan with what Strava shows and adapt the coming weeks ("Check-in mode").
- **Read-out**: "how is my training going?", "what paces should I use?", "is my goal realistic?". Do steps 1-6 and answer the question. A plan is an offer here, not an obligation.

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
- `get_activity_streams` only for a within-run question (fade in a long run, rep paces when laps don't help): ask for `["time","distance","heart_rate"]` with `resolution` 100-300 and compute pace from distance and time differences; `velocity_smooth` samples are instantaneous and noisy.
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

**Plan lint** (step 8): `python3 runcoach.py check`.

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
2. **Pull**: call 3 over at least the last 8 weeks, then `digest`, plus detail calls for the key sessions of the period.
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

## What the evidence supports

- **Reasonably supported.** Sudden jumps in a single run raise overuse-injury risk: in a 2025 cohort of 5,205 runners, runs more than 10% longer than the longest of the previous 30 days carried roughly 1.5 to 2.3 times the injury rate. A previous injury is the most consistent predictor of the next one. Newer runners are injured more often per hour than established ones. Mostly-easy training with a small dose of hard work. A taper of about two weeks that cuts volume by 41-60% and keeps intensity. Strength training improves running economy.
- **Convention: use it, don't oversell it.** The 10% weekly rule (a trial in novices found no benefit over a faster build; jumps above about 30% are the concern). Lighter weeks. One change at a time. The return-from-break percentages. Long-run time caps. Phase proportions. The goal-gap rule of thumb.
- **Not supported: avoid.** The ACWR "sweet spot" of 0.8-1.3 and any injury-risk percentage attached to it: it comes from team sports, and in that same runner cohort neither ACWR nor week-to-week change predicted injury the way the model claims. "Strength training cuts running injuries by X%": pooled trials in runners show no clear effect, except in supervised programmes. Claims that polarized beats pyramidal training or the reverse: differences are small and individual. Age-based maximum heart rate formulas treated as fact.

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

## The script

```python
# runcoach.py - the arithmetic for the Strava running coach skill (Python 3.8+, stdlib only).
#   digest : weekly load picture from a run list     paces : fitness anchor -> training paces, goal check
#   check  : lint a drafted plan                      (each subcommand has -h)
import argparse, math, statistics as st, sys
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
    for s in (p, q, c):
        s.add_argument("--unit", default="km", choices=["km", "mi"])
        s.add_argument("--today", default=str(date.today()))
    a = ap.parse_args()
    a.fn(a)
```
