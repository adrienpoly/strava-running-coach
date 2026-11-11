# Evals

Each folder is one test case in the layout `claude plugin eval` reads: `prompt.md` (the user's message), `case.yaml` (what a good result looks like), `graders/` (one checkable statement per file) and, for the offline cases, `files/` with the inputs.

| Case | What it tests |
|---|---|
| `marathon-plan-imperial` | A plan in miles from a clean but messy-in-places log: two duplicate uploads, a race measured long by GPS, a paused long run, stale pace zones. |
| `return-from-break-10k` | A runner back from five weeks off with a calf injury, asking in French for a time they could run before the break. |
| `checkin-after-illness` | A check-in: two plan weeks done, one lost to the flu, a first run back with a raised heart rate. |
| `live-strava-half-plan` | Needs a real Strava connector, so it has no fixtures and is not part of the offline numbers. |
| `activity-long-run-fade` | Feedback on one long run: 30% longer than anything in the previous month, started too fast, on a warm day, without fuel, with a stop and a fade. |
| `activity-intervals-too-fast` | Feedback in French on 6 x 1000 m with programmed laps: two reps far too fast, then slower every rep, although the average pace matches the target. |
| `activity-race-fast-start` | Feedback in miles on a 10K: first mile faster than 5K race pace, a second half 9% slower, a GPS distance that reads long. |

The Strava data is synthetic and the runners are invented. `tools/make_fixtures.py` generates it in the shape the connector returns; the test suite checks that the committed files match the generator. The three `activity-*` cases also carry the streams of the run in question, simulated second by second and sampled the way the connector samples them. "Today" is Tuesday 2 June 2026 in every offline case.

## Results

Fresh agents, one run per configuration, graded by hand against the statements in `graders/`. The three `activity-*` cases were added with the activity feedback mode and have not been run: the table has no row for them.

| Case | With skill | Without skill |
|---|---|---|
| marathon-plan-imperial | 14/14 | 14/14 |
| return-from-break-10k | 14/14 | 12/14 |
| checkin-after-illness | 9/10 | 9/10 |
| Mean pass rate | 97% | 92% |
| Mean tokens per run | 190k | 163k |
| Mean time per run | 11 min | 9 min 20 s |

What the numbers do and do not show:

- **The baseline is strong.** Given the same data and no skill, the model also removed the duplicate uploads, used the official race time, computed VDOT equivalents and gave an honest verdict on the goal. 34 of the 38 statements pass on both sides and separate nothing.
- **Where the skill made a difference.** In the return from injury, the plan without the skill lengthens the long run from 7 to 9 km in one step and adds 7 then 6 km to the weekly volume; with the skill both grow in small steps. Less measurable: with the skill, paces stay at current fitness until a checkpoint (the baseline starts goal-pace work earlier and schedules an all-out 5 km test six weeks after a calf tear), and replies keep the same structure.
- **Where it did not.** The check-in is as good without the skill. Both replies are longer than the 450 words the case allows; revising the skill cut its reply from 929 to 517 words.
- **Cost.** About 16% more tokens and 18% more time with the skill.
- **Limits.** One run each, so no variance estimate. One model, a capable one; weaker models were not tested. Two statements per plan case were added after a first round in which the original set separated nothing, and one statement that encoded the skill's own pace formula was relaxed. The cases have not been run through the `claude plugin eval` CLI.

The published skill includes small clarifications made after these runs (labels containing commas, dating the recent long run in `check`, wording). The unit tests cover the script side of them.

## Running them

With the [skill-creator](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills) loop: give a fresh agent the skill folder, the prompt and the case's `files/`, save its reply, and grade it against `graders/`. Do the same without the skill for a baseline.

With Claude Code, from the repository root: `claude plugin eval . --allow-tools Write,Edit,Bash --scaffold`. These are real, billed model runs.
If the scaffold scripts lost their executable bit on the way, restore it with `chmod +x evals/*/place-files.sh`.
