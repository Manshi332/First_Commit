# lifecycle.py
"""Ticket lifecycle state machine for CivicFlow.

NEW -> AI TRIAGED -> ASSIGNED -> IN PROGRESS -> AWAITING APPROVAL -> RESOLVED
    -> CITIZEN VERIFIED -> CLOSED

* NEW / AI TRIAGED / ASSIGNED are performed automatically by the AI agent.
* ASSIGNED -> IN PROGRESS is the crew dispatch (guarded by Cedar in app.py).
* AWAITING APPROVAL is only used when urgency >= 4 (officer sign-off).
  Lower-urgency tickets skip straight from IN PROGRESS to RESOLVED.
* RESOLVED -> IN PROGRESS is a "citizen disputes the fix" re-open.
"""
from dataclasses import dataclass
from datetime import timedelta

STATES = [
    "NEW", "AI TRIAGED", "ASSIGNED", "IN PROGRESS",
    "AWAITING APPROVAL", "RESOLVED", "CITIZEN VERIFIED", "CLOSED",
]
STATE_LABELS = {
    "NEW": "New",
    "AI TRIAGED": "AI Triaged",
    "ASSIGNED": "Assigned",
    "IN PROGRESS": "In Progress",
    "AWAITING APPROVAL": "Awaiting Approval",
    "RESOLVED": "Resolved",
    "CITIZEN VERIFIED": "Citizen Verified",
    "CLOSED": "Closed",
}
DONE_STATES = {"RESOLVED", "CITIZEN VERIFIED", "CLOSED"}
PRE_DISPATCH_STATES = ("NEW", "AI TRIAGED", "ASSIGNED")
APPROVAL_URGENCY = 4

STAFF = ("FieldTechnician", "MunicipalOfficer", "Supervisor")
OFFICERS = ("MunicipalOfficer", "Supervisor")
ROLES = STAFF + ("Citizen",)


@dataclass(frozen=True)
class Action:
    target: str
    label: str
    roles: tuple
    cedar: bool = False          # True -> caller must pass a Cedar check first
    needs_evidence: bool = False  # True -> ticket['resolution'] must exist


# ------------------------------------------------------------------ helpers
def is_active(t: dict) -> bool:
    return t["state"] not in DONE_STATES


def needs_approval(t: dict) -> bool:
    return t["urgency"] >= APPROVAL_URGENCY


def new_ticket(ticket_id, category, location_key, ward, team, title, urgency,
               priority_label, recommended_action, evidence, created_at,
               reports_count=1, lat=0.0, lon=0.0, reporters=(), report_times=None,
               dispatch_cost=0) -> dict:
    return {
        "ticket_id": ticket_id,
        "category": category,
        "location_key": location_key,
        "ward": ward,
        "team": team,
        "title": title,
        "reports_count": reports_count,
        "urgency": urgency,
        "priority_label": priority_label,
        "recommended_action": recommended_action,
        "evidence_list": list(evidence),
        "created_at": created_at,
        "latest_report": created_at,
        "resolved_at": None,
        "state": "NEW",
        "escalation_level": 0,
        "lat": lat,
        "lon": lon,
        "reporters": set(reporters),
        "report_times": list(report_times) if report_times else [created_at] * reports_count,
        "dispatch_cost": dispatch_cost,
        "authz": [],                 # Cedar decisions
        "resolution": None,          # evidence submitted by the officer
        "resolution_history": [],
        "reopen_count": 0,
        "dispute_reason": None,
        "language": "English",
        "translation": None,
        "history": [{"kind": "transition", "state": "NEW", "at": created_at,
                     "actor": "Citizen", "note": "Complaint received"}],
    }


def _set_state(t, state, actor, at, note=""):
    t["state"] = state
    if state == "RESOLVED":
        t["resolved_at"] = at          # SLA clock stops
    elif state == "IN PROGRESS":
        t["resolved_at"] = None        # re-open restarts the clock
    t["history"].append({"kind": "transition", "state": state, "at": at,
                         "actor": actor, "note": note})


def add_note(t, actor, at, note):
    t["history"].append({"kind": "note", "state": t["state"], "at": at,
                         "actor": actor, "note": note})


def auto_triage(t, at):
    """NEW -> AI TRIAGED -> ASSIGNED, done by the AI agent."""
    _set_state(t, "AI TRIAGED", "AI Agent", at,
               f"Classified as {t['category']}, urgency {t['urgency']}/5")
    _set_state(t, "ASSIGNED", "AI Agent", at, f"Routed to {t['team']}")


def fast_forward(t, target, start):
    """Seed helper: walk a ticket forward to `target` with synthetic timestamps."""
    idx_target = STATES.index(target)
    for i, s in enumerate(STATES):
        if i <= STATES.index(t["state"]) or i > idx_target:
            continue
        if s == "AWAITING APPROVAL" and not needs_approval(t):
            continue
        _set_state(t, s, "System (seed)", start + timedelta(minutes=2 * i))


# ------------------------------------------------------------- transitions
def available_actions(t: dict) -> list:
    s = t["state"]
    if s == "ASSIGNED":
        return [Action("IN PROGRESS", "🚒 Dispatch crew (Cedar-checked)", STAFF, cedar=True)]
    if s == "IN PROGRESS":
        if needs_approval(t):
            return [Action("AWAITING APPROVAL", "📝 Submit resolution for officer approval", STAFF,
                           needs_evidence=True)]
        return [Action("RESOLVED", "✅ Submit resolution", STAFF, needs_evidence=True)]
    if s == "AWAITING APPROVAL":
        return [Action("RESOLVED", "✅ Approve & mark resolved", OFFICERS)]
    if s == "RESOLVED":
        return [Action("CITIZEN VERIFIED", "🙋 Citizen confirms the fix", ("Citizen",)),
                Action("IN PROGRESS", "↩️ Citizen disputes — re-open", ("Citizen",))]
    if s == "CITIZEN VERIFIED":
        return [Action("CLOSED", "🔒 Close ticket", OFFICERS)]
    return []


def advance(t, target, actor, at, note=""):
    action = next((a for a in available_actions(t) if a.target == target), None)
    if action is None:
        return False, f"Invalid transition {t['state']} → {target}."
    if actor not in action.roles:
        return False, f"{actor} cannot do this step (requires {', '.join(action.roles)})."
    if action.needs_evidence and not t.get("resolution"):
        return False, "Resolution evidence (photo) is required before this ticket can be resolved."
    prev = t["state"]
    _set_state(t, target, actor, at, note)
    return True, f"{t['ticket_id']}: {prev} → {target}"


# ---------------------------------------------------------------------- UI
GREEN, AMBER, GREY = "#16A34A", "#F59E0B", "#9CA3AF"


def render_tracker_html(t: dict) -> str:
    cur = STATES.index(t["state"])
    last = {}
    for h in t["history"]:
        if h["kind"] == "transition":
            last[h["state"]] = h
    parts = [f'<div style="font-weight:700;font-size:17px;margin-bottom:8px;">{t["ticket_id"]}</div>']
    for i, s in enumerate(STATES):
        skipped = s == "AWAITING APPROVAL" and not needs_approval(t)
        if skipped:
            marker, col, weight, txt = "◌", GREY, "400", GREY
            meta = "skipped (urgency &lt; 4)"
        elif i < cur:
            marker, col, weight, txt = "●", GREEN, "500", "inherit"
            h = last.get(s)
            meta = f'{h["at"]:%H:%M} · {h["actor"]}' if h else ""
        elif i == cur:
            marker, col, weight, txt = "◉", AMBER, "700", "inherit"
            h = last.get(s)
            meta = (f'{h["at"]:%H:%M} · {h["actor"]} · <b>current</b>' if h else "<b>current</b>")
        else:
            marker, col, weight, txt = "○", GREY, "400", GREY
            meta = ""
        line = ""
        if i < len(STATES) - 1:
            line = (f'<div style="width:2px;height:18px;margin:2px 0;'
                    f'background:{GREEN if i < cur else GREY};"></div>')
        parts.append(
            '<div style="display:flex;gap:12px;">'
            '<div style="display:flex;flex-direction:column;align-items:center;width:20px;">'
            f'<div style="font-size:18px;line-height:18px;color:{col};">{marker}</div>{line}</div>'
            f'<div style="padding-bottom:4px;"><span style="font-weight:{weight};color:{txt};">'
            f'{STATE_LABELS[s]}</span> <span style="font-size:12px;color:{GREY};">{meta}</span></div></div>'
        )
    return "".join(parts)
