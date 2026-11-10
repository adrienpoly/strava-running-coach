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
