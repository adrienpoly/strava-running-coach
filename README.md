# strava-running-coach

A [Claude skill](https://support.claude.com/en/articles/12512180-use-skills-in-claude) that builds, checks and adapts running training plans from the runner's own Strava data.

Claude reads the training log through the Strava connector, cleans it, and hands the arithmetic to a small tested script. Then it does the coaching: a picture of where the runner is, an honest verdict on the goal, a plan that grows out of what they actually do, check-ins that compare the plan with what Strava shows, and feedback on a single run.

## What it does

- **Plan.** A training plan toward a race (5K to marathon) or a fitness goal, with paces taken from current fitness, not from the goal time.
- **Check-in.** Planned versus done, read from Strava, and the next weeks adjusted: a missed week, an illness, a session that went too well.
- **Run feedback.** One run, workout or race, read from its splits, laps and heart rate against the runner's own recent running: was the easy run easy, where the long run faded and why, whether the reps hit their target, how the race was paced.
- **Read-out.** "How is my training going?", "What paces should I use?", "Is 1:55 realistic?" answered from the data, without forcing a plan on anyone.

It answers in the runner's language and units.

## Requirements

- A Claude surface that supports skills, with the **Strava connector** enabled (Strava requires a subscription for it). Without Strava the skill falls back to what the runner reports and marks the plan provisional.
- **Code execution**, for the script. Without it the skill uses a small pace table and says its figures are approximate.

## Install

**Claude apps (claude.ai, desktop).** Download [`dist/strava-running-coach.zip`](dist/strava-running-coach.zip), then go to Customize > Skills, click "+", "Create skill", "Upload a skill", and pick the ZIP. Code execution must be on (Settings > Capabilities).

**Claude Code.**

```bash
git clone https://github.com/adrienpoly/strava-running-coach ~/.claude/skills/strava-running-coach
```

**One file.** [`dist/SKILL.md`](dist/SKILL.md) is the whole skill with the script embedded, for install paths that take a single SKILL.md.

Then ask for what you want: "Build me a plan for a half marathon on 7 March, I'd like to break 1:55", "check-in", "is my easy pace right?", "what went wrong in my 10K on Sunday?".

## How it works

1. **Pull.** Eight read-only connector calls: profile, zones, twelve weeks of runs, the year's longest runs, races, dated best efforts, other sports.
2. **Clean and classify.** Each run gets a kind (easy, long, workout, race, other) from its tags, name and description. Duplicate uploads, race-day warm-ups and "runs" that are not runs are handled before any number is trusted.
3. **Compute.** `scripts/runcoach.py` has four subcommands:
   - `digest`: weekly table, baseline volume three ways, breaks, run days, the long-run ceiling, typical easy pace, flags.
   - `paces`: VDOT from races and best efforts, equivalent times, training pace ranges, a goal verdict, and a discount after a layoff.
   - `check`: a lint for a drafted plan (volume spikes, the long-run ceiling, taper, calendar dates).
   - `activity`: one run from its streams and laps: splits, halves and quarters, heart-rate drift, stops, time in zones, repetitions against a target pace.
4. **Read like a coach.** How long the runner has really been running, whether easy runs are easy (decided by heart rate, not by a pace table), where endurance or speed is the limiter, what else they train.
5. **Show the picture, ask only what data cannot know.** Goal, availability, niggles, anything untracked.
6. **Reality-check the goal**, with an A goal, a B goal and a checkpoint.
7. **Design and lint the plan**, then deliver it: where you are, the goal, paces, the plan at a glance, the next weeks in detail, race day, how to adapt.

```text
$ python3 scripts/runcoach.py paces --today 2026-06-02 --result hm,1:47:30,2026-04-19,race --goal m,3:40:00 --weeks 18 --unit mi
RESULTS
     hm  1:47:30  VDOT 41.5   6 wk ago  race
ANCHOR  VDOT 41.5 from hm 1:47:30
EQUIVALENTS at this VDOT (optimistic for distances longer than the anchor unless the endurance is trained)
  5k 23:22 (7:31/mi) | 10k 48:29 (7:48/mi) | hm 1:47:30 (8:12/mi) | m 3:42:50 (8:30/mi)
TRAINING PACES (/mi)
  easy 9:33-10:31 (fast end is a ceiling, slower is fine) | threshold 7:52-8:03 | interval 7:14-7:25 | reps about 6:56
GOAL  m 3:40:00 (8:23/mi) = VDOT 42.1; current equivalent 3:42:50; gap 1.3% -> realistic (rule of thumb ...)
```

## What it will not claim

The skill separates what is supported from what is convention, and says so to the runner.

- **Supported.** A single run more than 10% longer than the longest of the previous 30 days raises overuse-injury risk ([Frandsen et al., BJSM 2025](https://pure.au.dk/portal/en/publications/how-much-running-is-too-much-identifying-high-risk-running-sessio/), 5,205 runners). A taper of about two weeks that cuts volume by 41-60% and keeps intensity ([meta-analysis](https://pubmed.ncbi.nlm.nih.gov/17762369/)). Newer runners are injured more often per hour.
- **Convention.** The 10% weekly rule, lighter weeks, return-from-break percentages, long-run time caps. Useful, not laws.
- **Avoided.** The acute:chronic workload ratio and any injury-risk percentage: the ratio comes from team sports and did not predict injury in that runner cohort. "Strength training cuts running injuries by X%": [pooled trials in runners](https://lida.sport-iat.de/ta/Record/4086976) show no clear effect outside supervised programmes.

It is a coach, not a clinician. It gives a pain rule, sends anything worrying to a physiotherapist or doctor, and never comments on weight.

## Evals

Seven cases live in [`evals/`](evals/). Four cover plans and check-ins: a marathon plan in miles, a return from a calf injury, a check-in after the flu (all three on synthetic Strava data), and one that needs a live connector. Each of the three offline ones was run by a fresh agent with the skill and without it.

| Case | With skill | Without skill |
|---|---|---|
| marathon-plan-imperial | 14/14 | 14/14 |
| return-from-break-10k | 14/14 | 12/14 |
| checkin-after-illness | 9/10 | 9/10 |

Read this for what it is: one run per configuration, a capable model on both sides, and a baseline that is already good at this when it has the data. The skill costs about 16% more tokens. What it changed measurably is the rebuild after injury (long run and weekly volume grow in small steps instead of jumps). What it changed less measurably is that paces stay at current fitness until a checkpoint, and that every reply has the same shape. Details and caveats are in [`evals/README.md`](evals/README.md).

The other three cases cover feedback on one run: a long run that fades, intervals started too fast, a 10K paced badly. They are written, and the test suite checks that their data tells the story they rely on, but they have not been run yet, so there are no numbers for that mode.

## Development

```bash
python3 -m unittest discover -s tests -v   # script, fixtures and dist/ in sync
python3 tools/make_fixtures.py             # regenerate the synthetic Strava data
python3 tools/build_dist.py                # rebuild dist/ after editing SKILL.md or the script
```

The script needs Python 3.9 or later and nothing outside the standard library. Edit `SKILL.md` and `scripts/runcoach.py`; `dist/` is generated.

## Credits

This started as a critical review of [LightAxe/claude-running-coach](https://github.com/LightAxe/claude-running-coach) by Rob Ogilvie. It shares that project's goal and none of its text or code. The pace model is the Daniels and Gilbert oxygen-cost and duration formulas, checked against the published VDOT tables.

## License

[MIT](LICENSE)
