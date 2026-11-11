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
