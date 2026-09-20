"""Shared state, seed data and business actions for CivicFlow."""
import io
from datetime import datetime, timedelta

import streamlit as st
from PIL import Image, ImageDraw

import ai_insights
import cedar_eval
import geo_intel as geo
import lifecycle as lc
import opensearch_search as search
from dispatch_notifier import trigger_localstack_notification
from grievance_agent import process_complaint_locally

ss = st.session_state

LOCATION_COORDS = {
    "dayalpur": {"lat": 25.6833, "lon": 85.2167},
    "daulatpur": {"lat": 25.6833, "lon": 85.2167},
    "market": {"lat": 25.6110, "lon": 85.1440},
    "sector 4": {"lat": 25.6010, "lon": 85.1600},
    "default": {"lat": 25.5941, "lon": 85.1376},
}
LOCATION_ALIASES = {"daulatpur": "dayalpur"}

DEPT_DEFAULTS = {
    "Electrical & Power": ("Emergency Electrical Response Crew",
                           "Immediately isolate affected power grid line and dispatch emergency repair crew."),
    "Water Works": ("Rapid Utility Infrastructure Repair Team",
                    "Close main junction supply valve and deploy dewatering pumps and pipe repair unit."),
    "Sanitation & Waste Management": ("Sanitation & Hygiene Heavy Deployment Unit",
                                      "Schedule immediate mechanized waste pickup and conduct localized chemical spraying."),
    "Roads & Transit": ("Municipal Civil Infrastructure Repair Unit",
                        "Deploy temporary hazard barricading and schedule high-priority asphalt patching."),
}
PRIORITY = {5: "CRITICAL — 5/5", 4: "HIGH — 4/5", 3: "MEDIUM — 3/5", 2: "ROUTINE — 2/5", 1: "LOW — 1/5"}
COST_BASE = {"electr": 16000, "water": 12000, "road": 9000, "sanit": 6000}
COST_MULT = {5: 5, 4: 3, 3: 2, 2: 1, 1: 1}
BADGES = {5: "🔴 Critical", 4: "🟠 High", 3: "🟡 Medium", 2: "🟢 Low", 1: "🟢 Low"}


def inr(n) -> str:
    return f"₹{int(n):,}"


def estimate_cost(category: str, urgency: int) -> int:
    c = category.lower()
    base = next((v for k, v in COST_BASE.items() if k in c), 9000)
    return base * COST_MULT.get(int(urgency), 1)


def now() -> datetime:
    return datetime.now() + timedelta(minutes=ss.get("clock_offset_min", 0))


def flash(kind, msg):
    ss["flash"] = (kind, msg)


def show_flash():
    if ss.get("flash"):
        kind, msg = ss.pop("flash")
        getattr(st, kind)(msg)


def log_event(ticket, role, event, decision):
    ss["audit_log"].append({
        "Time": now().strftime("%H:%M:%S"), "Master Ticket": ticket["ticket_id"], "Event": event,
        "Actor": role, "Department": ticket["category"], "Ward": ticket["ward"],
        "Assigned Team": ticket["team"], "Urgency": ticket["urgency"], "Decision": decision})


def _reindex(ticket):
    """Push the latest ticket state into the OpenSearch index (Data & Search
    building block). No-op / fails silently if OpenSearch isn't running —
    see opensearch_search.py for the fallback story."""
    try:
        search.index_ticket(ticket)
    except Exception:
        pass


def placeholder_photo(text: str) -> bytes:
    img = Image.new("RGB", (480, 300), (34, 120, 84))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, 467, 287], outline=(255, 255, 255), width=3)
    d.text((30, 135), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def apply_language_detection(t: dict):
    """Runs the multilingual detector (ai_insights.py) over a ticket's
    evidence and stashes the result on the ticket for the UI to show."""
    raw = t["evidence_list"][-1] if t["evidence_list"] else t["title"]
    result = ai_insights.detect_and_translate(raw)
    t["language"] = result["language"]
    t["translation"] = result["translation"]


# ---------------------------------------------------------------- seed data
# (id, dept, location, ward, title, urgency, reports, minutes_ago, state, evidence, mine)
SEED = [
    # ---- older, already-closed tickets (baseline for the 24h-vs-24h hotspot comparison)
    ("CF-1030", "Electrical & Power", "dayalpur", "Ward 12", "Streetlights out on main road", 3, 5, 2400, "CLOSED", ["Report: Street lights out on main road"], False),
    ("CF-1031", "Water Works", "dayalpur", "Ward 12", "Pipe leakage near Dayalpur chowk", 3, 4, 2160, "CLOSED", ["Report: Pipe leaking near chowk"], False),
    ("CF-1032", "Roads & Transit", "dayalpur", "Ward 12", "Potholes on link road", 3, 10, 1800, "CLOSED", ["Report: Potholes on link road"], False),
    ("CF-1033", "Sanitation & Waste Management", "dayalpur", "Ward 12", "Overflowing dump yard", 2, 8, 1980, "CLOSED", ["Report: Dump yard overflowing"], False),
    ("CF-1034", "Water Works", "market", "Ward 9", "Hydrant leakage at market", 3, 5, 1680, "CLOSED", ["Report: Hydrant leaking"], False),
    ("CF-1037", "Sanitation & Waste Management", "market", "Ward 9", "Uncollected waste behind market", 2, 6, 1800, "CLOSED", ["Report: Waste not collected"], False),
    ("CF-1035", "Roads & Transit", "sector 4", "Ward 4", "Broken road edge at Sector 4", 2, 4, 2100, "CLOSED", ["Report: Road edge broken"], False),
    ("CF-1036", "Electrical & Power", "sector 4", "Ward 4", "Transformer noise at Sector 4", 2, 3, 2460, "CLOSED", ["Report: Transformer humming loudly"], False),
    # ---- current tickets
    ("CF-1041", "Sanitation & Waste Management", "market", "Ward 9", "Garbage pile near market drain", 2, 6, 300, "RESOLVED", ["Report: Kachra jama hai naali ke paas"], True),
    ("CF-1042", "Electrical & Power", "dayalpur", "Ward 12", "Exposed high-voltage cable near school street", 5, 5, 22, "ASSIGNED",
     ["Original report: High voltage cable snapped near school",
      "Voice report: Bijli ka taar toot kar school ke paas latak raha hai",
      "Photo upload: Snapped cable near school gate",
      "Report: Live wire sparking outside school gate",
      "Report: Cable hanging low, children cross here"], True),
    ("CF-1043", "Roads & Transit", "dayalpur", "Ward 12", "Large pothole near school street", 4, 12, 95, "IN PROGRESS",
     ["Original report: Large pothole near school street", "Voice report: Sadak par bohot bada gaddha hai"], True),
    ("CF-1044", "Water Works", "market", "Ward 9", "Water main burst flooding market chowk", 4, 7, 20, "ASSIGNED", ["Report: Paani ka pipe phat gaya hai"], False),
    ("CF-1046", "Electrical & Power", "sector 4", "Ward 4", "Street light pole cover loose", 2, 3, 300, "IN PROGRESS", ["Report: Street light pole 14 cover is loose"], True),
    ("CF-1047", "Sanitation & Waste Management", "market", "Ward 9", "Overflowing bins behind market", 3, 5, 40, "ASSIGNED", ["Report: Bins overflowing"], False),
    ("CF-1048", "Roads & Transit", "sector 4", "Ward 4", "Broken footpath slabs at Sector 4", 3, 6, 60, "ASSIGNED", ["Report: Footpath slabs broken"], False),
    ("CF-1049", "Water Works", "dayalpur", "Ward 12", "Low pressure and leaking joint", 3, 7, 120, "IN PROGRESS", ["Report: Paani ka pressure kam aur leakage"], False),
    ("CF-1050", "Sanitation & Waste Management", "dayalpur", "Ward 12", "Garbage not collected for 4 days", 2, 8, 360, "ASSIGNED", ["Report: Kachra gaadi 4 din se nahi aayi"], False),
    ("CF-1051", "Electrical & Power", "dayalpur", "Ward 12", "Transformer sparking near Dayalpur chowk", 4, 9, 360, "IN PROGRESS", ["Report: Transformer sparking at chowk"], False),
]


def _build_seed() -> dict:
    tickets, base = {}, now()
    for tid, dept, loc, ward, title, urg, reps, ago, state, ev, mine in SEED:
        team, action = DEPT_DEFAULTS[dept]
        created = base - timedelta(minutes=ago)
        spread = min(ago * 0.5, 180)
        times = [created + timedelta(minutes=spread * i / max(reps - 1, 1)) for i in range(reps)]
        lat, lon = geo.jitter(LOCATION_COORDS[loc]["lat"], LOCATION_COORDS[loc]["lon"], tid)
        t = lc.new_ticket(tid, dept, loc, ward, team, title, urg, PRIORITY[urg], action, ev, created,
                          reps, lat, lon, {"me"} if mine else (), times, estimate_cost(dept, urg))
        apply_language_detection(t)
        lc.auto_triage(t, created)
        lc.fast_forward(t, state, created)
        if state in ("RESOLVED", "CITIZEN VERIFIED", "CLOSED") and mine:
            t["resolution"] = {
                "photo": placeholder_photo("Repair completed (demo photo)"), "filename": "repair_done.png",
                "notes": "Waste cleared and drain flushed.", "verdict": "VERIFIED", "mode": "heuristic",
                "checks": [], "flagged": False, "by": "MunicipalOfficer", "at": t["resolved_at"]}
        tickets[tid] = t
    return tickets


def init_state():
    ss.setdefault("total_processed", 0)
    ss.setdefault("audit_log", [])
    ss.setdefault("clock_offset_min", 0)
    ss.setdefault("flash", None)
    ss.setdefault("vision_cache", {})
    if "master_tickets" not in ss:
        ss["master_tickets"] = _build_seed()
        ss["next_ticket_num"] = 1052
        # Data & Search: seed the OpenSearch index once, at startup, so the
        # search bar has something to query on the very first page load.
        try:
            search.reindex_all(ss["master_tickets"])
        except Exception:
            pass


def tickets() -> dict:
    return ss["master_tickets"]


# ------------------------------------------------------------------- intake
def _get(data, key, default=""):
    return data.get(key, default) if isinstance(data, dict) else getattr(data, key, default)


def ingest_complaint(raw: str):
    ts = now()
    res = process_complaint_locally(raw)
    ss["total_processed"] += 1
    dept = _get(res, "department", "Roads & Transit")
    ward = _get(res, "ward", "Ward 12")
    team = _get(res, "team", DEPT_DEFAULTS["Roads & Transit"][0])
    urgency = int(_get(res, "urgency", 2))
    label = _get(res, "priority_label", PRIORITY.get(urgency, "ROUTINE — 2/5"))
    action = _get(res, "recommended_action", "Inspect site.")
    hint = str(_get(res, "location_hint", "")).lower()
    lang_result = ai_insights.detect_and_translate(raw)

    loc = "default"
    for key in LOCATION_COORDS:
        if key != "default" and (key in raw.lower() or key in hint):
            loc = key
            break
    loc = LOCATION_ALIASES.get(loc, loc)

    match = None
    if loc != "default":
        match = next((t for t in tickets().values() if lc.is_active(t)
                      and t["category"] == dept and t["location_key"] == loc), None)
    if match:
        match["reports_count"] += 1
        match["latest_report"] = ts
        match["report_times"].append(ts)
        match["reporters"].add("me")
        match["evidence_list"].append(raw)
        match["language"] = lang_result["language"]
        match["translation"] = lang_result["translation"]
        if urgency > match["urgency"]:
            lc.add_note(match, "AI Agent", ts, f"Urgency raised {match['urgency']} → {urgency} by duplicate report")
            match["urgency"], match["priority_label"] = urgency, label
            match["dispatch_cost"] = estimate_cost(dept, urgency)
        else:
            lc.add_note(match, "AI Agent", ts, "Duplicate citizen report merged")
        ss["active_result"] = {"type": "DUPLICATE", "master_id": match["ticket_id"]}
        ss["selected_ticket"] = match["ticket_id"]
        log_event(match, "AI Agent", "Duplicate report merged", "MERGED")
        _reindex(match)
        flash("warning", f"🔄 Duplicate detected — your report was merged into {match['ticket_id']} "
                         f"({match['reports_count']} reports).")
    else:
        tid = f"CF-{ss['next_ticket_num']}"
        ss["next_ticket_num"] += 1
        lat, lon = geo.jitter(LOCATION_COORDS[loc]["lat"], LOCATION_COORDS[loc]["lon"], tid)
        t = lc.new_ticket(tid, dept, loc, ward, team, raw[:50] + "...", urgency, label, action, [raw], ts,
                          1, lat, lon, {"me"}, [ts], estimate_cost(dept, urgency))
        t["language"] = lang_result["language"]
        t["translation"] = lang_result["translation"]
        lc.auto_triage(t, ts)
        tickets()[tid] = t
        ss["active_result"] = {"type": "NEW", "master_id": tid}
        ss["selected_ticket"] = tid
        log_event(t, "AI Agent", "NEW → AI TRIAGED → ASSIGNED", "AUTO")
        _reindex(t)
        flash("success", f"🆕 Ticket {tid} created and assigned to {team}.")


# ------------------------------------------------------- staff-side actions
def dispatch_crew(ticket, role):
    ts = now()
    d = cedar_eval.authorize(role, "ApproveDispatch", {
        "ticket_id": ticket["ticket_id"], "category": ticket["category"],
        "urgency": ticket["urgency"], "cost": ticket["dispatch_cost"]})
    d["at"] = ts
    ticket["authz"].append(d)
    log_event(ticket, role, f"Dispatch authorization ({inr(d['cost'])})", "ALLOWED" if d["allowed"] else "DENIED")
    if not d["allowed"]:
        flash("error", f"🚫 Dispatch blocked for {role}. {d['reason']}  Open “Authorization Details” below.")
        return
    sent = trigger_localstack_notification(ticket["ticket_id"], ticket["category"], ticket["urgency"], role)
    ok, msg = lc.advance(ticket, "IN PROGRESS", role, ts, note="Crew dispatched")
    if not ok:
        flash("error", msg)
        return
    log_event(ticket, role, "ASSIGNED → IN PROGRESS", "ALLOWED")
    _reindex(ticket)
    flash("success", f"✅ {msg}. Crew dispatched." + (" 📡 SNS event published." if sent
                                                       else " (LocalStack offline — event recorded locally.)"))


def do_step(ticket, action, role):
    ts, prev = now(), ticket["state"]
    ok, msg = lc.advance(ticket, action.target, role, ts, note=action.label)
    if not ok:
        flash("error", msg)
        return
    log_event(ticket, role, f"{prev} → {action.target}", "ALLOWED")
    _reindex(ticket)
    flash("success", f"✅ {msg}")


def submit_resolution(ticket, role, photo, filename, notes, result, flagged):
    ts, prev = now(), ticket["state"]
    target = "AWAITING APPROVAL" if lc.needs_approval(ticket) else "RESOLVED"
    ticket["resolution"] = {"photo": photo, "filename": filename, "notes": notes, "verdict": result["verdict"],
                            "mode": result["mode"], "checks": result["checks"], "flagged": flagged,
                            "by": role, "at": ts}
    ok, msg = lc.advance(ticket, target, role, ts,
                         note="Resolution evidence submitted" + (" — FLAGGED for review" if flagged else ""))
    if not ok:
        ticket["resolution"] = None
        flash("error", msg)
        return
    log_event(ticket, role, f"{prev} → {target} (evidence: {result['verdict']})", "FLAGGED" if flagged else "ALLOWED")
    _reindex(ticket)
    flash("success", f"✅ RESOLUTION {result['verdict']} — {msg}")


# ---------------------------------------------------------- citizen closure
def citizen_respond(ticket, satisfied: bool, reason: str = ""):
    ts = now()
    if satisfied:
        ok, msg = lc.advance(ticket, "CITIZEN VERIFIED", "Citizen", ts, note="Citizen confirmed the fix")
        if ok:
            log_event(ticket, "Citizen", "Citizen confirmed resolution", "VERIFIED")
            _reindex(ticket)
            flash("success", "🙏 Thank you! Your confirmation has been recorded.")
        return
    if not reason.strip():
        flash("warning", "Please tell us what is still wrong before pressing 👎.")
        return
    if ticket.get("resolution"):
        ticket["resolution_history"].append(ticket["resolution"])
        ticket["resolution"] = None
    ok, msg = lc.advance(ticket, "IN PROGRESS", "Citizen", ts, note="Citizen disputed the fix")
    if not ok:
        flash("error", msg)
        return
    ticket["reopen_count"] += 1
    ticket["dispute_reason"] = reason.strip()
    ticket["escalation_level"] = 2
    lc.add_note(ticket, "SLA Engine", ts,
                f"Citizen disputed resolution (“{reason.strip()}”) — escalated to Supervisor")
    log_event(ticket, "Citizen", "Resolution disputed → re-opened → escalated to Supervisor", "ESCALATED")
    _reindex(ticket)
    flash("warning", "🔁 Complaint reopened · reason recorded · escalated to Supervisor.")