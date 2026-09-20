# ai_insights.py
"""Deterministic, fully-local "AI" helpers that power three CivicFlow features:

1. Multilingual detection + gloss-translation (English / Hindi / Hinglish),
   shown to citizens and officers so nobody has to guess what a complaint says.
2. AI-generated case summaries — a short, structured brief so an officer never
   has to read a raw citizen message to understand a ticket.
3. City-wide "what should I fix first" priority briefs for supervisors, built
   on top of the existing hotspot engine (hotspots.py) plus raw ticket signals.

Everything below is rule-based / dictionary-based on purpose: it needs no
network call and every output is traceable to the input data, which matches
the rest of CivicFlow's "explainable AI" design (see cedar_eval.py, evidence.py,
hotspots.py). A local LLM (the same Ollama agent used in grievance_agent.py)
could be swapped in later to refine the gloss-translation without changing
any of the call sites below.
"""
import re

import lifecycle as lc

# --------------------------------------------------------------------- lang
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

HINGLISH_MARKERS = {
    "hai", "nahi", "nahin", "bohot", "bahut", "kal", "aaj", "paani", "kachra",
    "bijli", "sadak", "gaddha", "gadha", "naali", "jama", "phat", "phata",
    "toot", "toota", "latak", "doob", "taar", "gaya", "gayi", "raha", "rahi",
    "wala", "chowk", "jaldi", "turant", "madad", "shikayat", "samasya", "din",
    "se", "ka", "ki", "ke", "me", "mein", "par", "aur", "hoga", "hogi",
    "aaya", "aayi", "nikal", "khula", "khuli", "yahan", "teen", "aa",
}

# A small word-for-word gloss dictionary — enough to produce a rough but
# readable English rendering of common civic Hindi/Hinglish phrases. This is
# a transparent substitution heuristic, not machine translation.
GLOSS = {
    "paani": "water", "ka": "of", "ki": "of", "ke": "of", "pipe": "pipe",
    "phat": "burst", "phata": "burst", "gaya": "", "gayi": "",
    "hai": "is", "nahi": "not", "nahin": "not", "bohot": "very", "bahut": "very",
    "bada": "big", "badi": "big", "sadak": "road", "doob": "flooded",
    "kachra": "garbage", "gaadi": "truck", "din": "days", "se": "for",
    "aayi": "come", "aaya": "come", "naali": "drain", "jama": "collected",
    "bijli": "electricity", "taar": "cable", "toot": "broken",
    "toota": "broken", "kar": "and", "latak": "hanging", "raha": "",
    "rahi": "", "paas": "near", "chowk": "junction",
    "immediate": "immediate", "action": "action", "required": "required",
    "loose": "loose", "sir": "sir", "kal": "yesterday", "yahan": "here",
    "teen": "three", "aa": "coming", "poori": "whole", "picchle": "last",
    "hamare": "our", "area": "area", "kam": "low", "pressure": "pressure",
    "leakage": "leakage", "aur": "and", "me": "in", "mein": "in",
}


def detect_language(text: str) -> str:
    """Cheap, explainable rule: Devanagari -> Hindi; romanized civic
    vocabulary -> Hinglish; otherwise English."""
    if DEVANAGARI_RE.search(text):
        return "Hindi"
    words = re.findall(r"[a-zA-Z]+", text.lower())
    hits = sum(1 for w in words if w in HINGLISH_MARKERS)
    if not words:
        return "English"
    if hits >= 2 or hits / len(words) >= 0.2:
        return "Hinglish"
    return "English"


def gloss_translate(text: str) -> str:
    """Best-effort English gloss of a Hinglish/romanized-Hindi sentence."""
    tokens = re.findall(r"[A-Za-z]+|[^\sA-Za-z]+", text)
    out = []
    for tok in tokens:
        low = tok.lower().strip(".,!?")
        if low in GLOSS:
            g = GLOSS[low]
            if g:
                out.append(g)
        else:
            out.append(tok)
    rendered = " ".join(out)
    rendered = re.sub(r"\s+([.,!?])", r"\1", rendered)
    rendered = re.sub(r"\s{2,}", " ", rendered).strip()
    if not rendered:
        return text
    return rendered[0].upper() + rendered[1:]


def detect_and_translate(raw_text: str) -> dict:
    """Returns {'language': ..., 'translation': str|None}. translation is
    None for English text (nothing to translate)."""
    lang = detect_language(raw_text)
    if lang == "English":
        return {"language": "English", "translation": None}
    return {"language": lang, "translation": gloss_translate(raw_text)}


# --------------------------------------------------------------- summaries
IMPACT_KEYWORDS = [
    ("live wire", "Immediate electrocution risk"),
    ("high voltage", "Immediate electrocution risk"),
    ("spark", "Fire / shock hazard to the public"),
    ("snapped", "Structural hazard — cable/pole down"),
    ("hanging", "Low-hanging hazard over a public path"),
    ("children", "Risk to school children"),
    ("school", "Near a school — child-safety risk"),
    ("doob", "Road/area partially flooded"),
    ("flood", "Road/area partially flooded"),
    ("overflow", "Public-health / hygiene risk"),
    ("blocked", "Access blocked"),
    ("no water", "Water supply disrupted"),
    ("not collected", "Waste accumulation risk"),
    ("market", "Disruption to a busy commercial area"),
]


def _duration_phrase(created_at, now):
    mins = (now - created_at).total_seconds() / 60
    if mins < 60:
        return f"{max(int(mins), 0)} min"
    if mins < 24 * 60:
        return f"{mins / 60:.1f} hours"
    return f"{mins / 1440:.1f} days"


def generate_case_summary(ticket: dict, now) -> dict:
    """AI-generated case summary: what an officer needs, nothing more."""
    text = " ".join(ticket["evidence_list"] + [ticket["title"]]).lower()
    impacts, seen = [], set()
    for kw, label in IMPACT_KEYWORDS:
        if kw in text and label not in seen:
            impacts.append(label)
            seen.add(label)
    if not impacts:
        impacts = ["Standard civic maintenance issue — no elevated public-safety signal detected."]

    location = ticket["ward"]
    if ticket.get("location_key") and ticket["location_key"] != "default":
        location += f", near {ticket['location_key'].title()}"

    return {
        "problem": ticket["title"].rstrip("."),
        "location": location,
        "duration": _duration_phrase(ticket["created_at"], now),
        "impact": impacts,
        "priority": ticket["priority_label"],
        "recommended_action": ticket["recommended_action"],
        "reports": ticket["reports_count"],
    }


# --------------------------------------------------------------- priority brief
def generate_priority_brief(tickets: dict, hotspots_list: list, now, top_n: int = 3) -> list:
    """'What should I fix first?' — ranks wards using AI hotspot scores
    (hotspots.py) blended with raw open-ticket signals, so a ward with a
    concentration of critical/breached tickets can surface even without a
    24h volume spike."""
    ward_stats = {}
    for t in tickets.values():
        if not lc.is_active(t):
            continue
        w = ward_stats.setdefault(t["ward"], {"complaints": 0, "critical": 0, "cats": {}})
        w["complaints"] += t["reports_count"]
        if t["urgency"] >= 4:
            w["critical"] += 1
        w["cats"][t["category"]] = w["cats"].get(t["category"], 0) + 1

    hotspot_map = {h["ward"]: h for h in hotspots_list}
    briefs = []
    for ward in set(ward_stats) | set(hotspot_map):
        st_ = ward_stats.get(ward, {"complaints": 0, "critical": 0, "cats": {}})
        h = hotspot_map.get(ward)
        top_cat = (max(st_["cats"], key=st_["cats"].get) if st_["cats"]
                   else (h["trends"][0]["dept"] if h else "General"))
        score = (h["score"] if h else 0) + st_["critical"] * 5 + st_["complaints"]
        if score <= 0:
            continue
        if h:
            recommendation = h["recommendation"]
            trend_note = (f"{h['recent_total']} complaints in the last 24h vs {h['prior_total']} prior"
                          + (f" ({h['growth_total']:+.0%})" if h["growth_total"] is not None else " (new activity)"))
        else:
            recommendation = f"Send a field inspector to {ward} for {top_cat}."
            trend_note = f"{st_['complaints']} active complaint(s), {st_['critical']} critical"
        briefs.append({
            "ward": ward, "score": score, "department": top_cat,
            "complaints": st_["complaints"], "critical": st_["critical"],
            "trend_note": trend_note, "recommendation": recommendation,
        })
    briefs.sort(key=lambda b: b["score"], reverse=True)
    tiers = ["🔴 PRIORITY 1", "🟠 PRIORITY 2", "🟡 PRIORITY 3", "🟢 PRIORITY 4", "🟢 PRIORITY 5"]
    for i, b in enumerate(briefs[:top_n]):
        b["rank"] = i + 1
        b["tier"] = tiers[min(i, len(tiers) - 1)]
    return briefs[:top_n]
