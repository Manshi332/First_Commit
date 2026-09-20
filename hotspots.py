# hotspots.py
"""AI hotspot detection: compares each ward's complaint volume in the last 24h
against the previous 24h, per department, and explains *why* a ward is flagged.
Fully deterministic, so every claim on the dashboard can be traced to numbers."""
from datetime import timedelta

import lifecycle as lc
from geo_intel import dept_style

WINDOW = timedelta(hours=24)
MIN_RECENT_HOTSPOT = 10     # complaints in last 24h
MIN_RECENT_WATCH = 6
GROWTH_TRIGGER = 0.25       # +25% overall
RISING_GROWTH = 0.50        # a department is "rising" at +50% ...
RISING_MIN = 3              # ... with at least 3 complaints

HINTS = {
    "Electrical": "Inspect feeder lines, transformers and cable condition.",
    "Water": "Inspect main-line pressure, joints and valves.",
    "Roads": "Survey road surface and drainage.",
    "Sanitation": "Review collection-route coverage and bin capacity.",
}


def _growth(recent, prior):
    return None if prior == 0 else (recent - prior) / prior


def _fmt_trend(x):
    if x["growth"] is None:
        return f"{x['dept']} complaints: new ({x['recent']} vs 0)"
    return f"{x['dept']} complaints: {x['growth']:+.0%} ({x['recent']} vs {x['prior']})"


def detect_hotspots(tickets: dict, now) -> list:
    buckets = {}
    for t in tickets.values():
        label = dept_style(t["category"])[0]
        for ts in t["report_times"]:
            age = now - ts
            if age < timedelta(0) or age > 2 * WINDOW:
                continue
            key = "recent" if age <= WINDOW else "prior"
            b = buckets.setdefault(t["ward"], {"recent": {}, "prior": {}})
            b[key][label] = b[key].get(label, 0) + 1

    out = []
    for ward, b in buckets.items():
        rt, pt = sum(b["recent"].values()), sum(b["prior"].values())
        g = _growth(rt, pt)
        g_eff = g if g is not None else (1.0 if rt else 0.0)

        trends = []
        for label in set(b["recent"]) | set(b["prior"]):
            r, p = b["recent"].get(label, 0), b["prior"].get(label, 0)
            gr = _growth(r, p)
            trends.append({"dept": label, "recent": r, "prior": p, "growth": gr,
                           "rising": r >= RISING_MIN and (gr is None or gr >= RISING_GROWTH)})
        trends.sort(key=lambda x: (x["growth"] if x["growth"] is not None else 99, x["recent"]),
                    reverse=True)
        rising = [x["dept"] for x in trends if x["rising"]]

        if rt >= MIN_RECENT_HOTSPOT and (g_eff >= GROWTH_TRIGGER or len(rising) >= 2):
            status = "HOTSPOT"
        elif rt >= MIN_RECENT_WATCH and g_eff >= GROWTH_TRIGGER:
            status = "WATCH"
        else:
            continue

        open_critical = sum(1 for t in tickets.values()
                            if t["ward"] == ward and lc.is_active(t) and t["urgency"] >= 4)
        because = [_fmt_trend(x) for x in trends
                   if x["recent"] > 0 and (x["growth"] is None or x["growth"] > 0)]
        if open_critical:
            because.append(f"{open_critical} open high-priority ticket{'s' if open_critical != 1 else ''}")

        if {"Electrical", "Water"} <= set(rising):
            hint = ("Electrical and water complaints are surging together — check for a shared cause "
                    "(utility-corridor works, flooding or a failing substation) and send a joint inspection team.")
        elif rising:
            hint = HINTS.get(rising[0], "Send a field inspector.")
        else:
            hint = "Send a field inspector."

        out.append({
            "ward": ward, "status": status, "recent_total": rt, "prior_total": pt,
            "growth_total": g, "trends": trends, "rising": rising, "because": because,
            "score": rt * (1 + max(g_eff, 0)) + 4 * len(rising) + 2 * open_critical,
            "headline": (f"{ward} is emerging as a civic hotspot." if status == "HOTSPOT"
                         else f"{ward} is on the AI watch list."),
            "recommendation": f"Investigate {ward} for possible infrastructure failure. {hint}"
                              if status == "HOTSPOT" else f"Monitor {ward} — {hint}",
        })
    out.sort(key=lambda h: h["score"], reverse=True)
    return out