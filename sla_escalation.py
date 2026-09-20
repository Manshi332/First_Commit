# sla_escalation.py
"""SLA tracking, automatic escalation and explainable escalation reasoning."""
import re

import lifecycle as lc

# Urgency -> response target (minutes)
SLA_MINUTES = {5: 30, 4: 120, 3: 720, 2: 1440, 1: 4320}

WARN_AT = 0.70        # >= 70% of SLA used  -> AT RISK
OFFICER_AT = 1.0      # SLA breached        -> Municipal Officer
SUPERVISOR_AT = 1.5   # 50% past the SLA    -> Supervisor

CHAIN = ["FieldTechnician", "MunicipalOfficer", "Supervisor"]
CHAIN_LABELS = {"FieldTechnician": "Field Technician",
                "MunicipalOfficer": "Municipal Officer",
                "Supervisor": "Supervisor"}

SENSITIVE_SITES = ["school", "hospital", "clinic", "college", "market",
                   "bus stand", "temple", "mosque", "aspatal"]
HAZARD_RE = r"high voltage|live wire|snapped|cable|gas leak|burst|collapse|open manhole|fire"


def fmt_duration(minutes: float) -> str:
    m = int(round(abs(minutes)))
    if m < 1:
        return "under 1 min"
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    if h >= 48:
        d, h = divmod(h, 24)
        return f"{d}d {h}h"
    return f"{h}h {r}m" if r else f"{h}h"


def sla_target(urgency: int) -> int:
    return SLA_MINUTES[max(1, min(5, int(urgency)))]


def sla_status(t: dict, now) -> dict:
    target = sla_target(t["urgency"])
    end = t["resolved_at"] or now
    elapsed = (end - t["created_at"]).total_seconds() / 60
    remaining = target - elapsed
    pct = elapsed / target

    if not lc.is_active(t):
        status = "MET" if elapsed <= target else "MISSED"
        level = t["escalation_level"]
        message = (f"✅ Resolved within SLA ({fmt_duration(elapsed)} of {fmt_duration(target)})"
                   if status == "MET" else
                   f"❌ Resolved {fmt_duration(-remaining)} after SLA deadline")
    else:
        if pct >= 1:
            status, message = "BREACHED", f"🚨 SLA BREACHED {fmt_duration(-remaining)} AGO"
        elif pct >= WARN_AT:
            status, message = "AT RISK", f"⚠️ SLA BREACH IN {fmt_duration(remaining)}"
        else:
            status, message = "ON TRACK", f"On track — {fmt_duration(remaining)} remaining"
        level = 2 if pct >= SUPERVISOR_AT else 1 if pct >= OFFICER_AT else 0
    return {"target": target, "elapsed": elapsed, "remaining": remaining,
            "pct": pct, "status": status, "level": level, "message": message}


def apply_escalations(tickets: dict, now) -> list:
    """Escalate every active ticket whose SLA has moved it up the chain.
    Idempotent: a ticket is only ever escalated *up*, once per level."""
    events = []
    for t in tickets.values():
        if not lc.is_active(t):
            continue
        s = sla_status(t, now)
        while t["escalation_level"] < s["level"]:
            frm = CHAIN_LABELS[CHAIN[t["escalation_level"]]]
            t["escalation_level"] += 1
            to = CHAIN_LABELS[CHAIN[t["escalation_level"]]]
            note = (f"SLA {fmt_duration(s['elapsed'])} elapsed of {fmt_duration(s['target'])} "
                    f"with no resolution — auto-escalated {frm} → {to}")
            lc.add_note(t, "SLA Engine", now, note)
            events.append((t, to, note))
    return events


def render_chain_html(level: int, active: bool = True) -> str:
    chips = []
    for i, role in enumerate(CHAIN):
        if i < level:
            style, mark = "background:#DCFCE7;color:#166534;", "✔ "
        elif i == level:
            style, mark = "background:#FEF3C7;color:#92400E;font-weight:700;", "● "
        else:
            style, mark = "background:#F3F4F6;color:#6B7280;", ""
        chips.append(f'<span style="padding:3px 9px;border-radius:12px;font-size:13px;{style}">'
                     f'{mark}{CHAIN_LABELS[role]}</span>')
    opacity = "1" if active else "0.55"
    return (f'<div style="margin:6px 0;opacity:{opacity};line-height:2.2;">'
            + ' <span style="color:#9CA3AF;">➜</span> '.join(chips) + "</div>")


def build_escalation_report(t: dict, status: dict):
    """Explainable escalation: returns None when no escalation is warranted."""
    if not lc.is_active(t):
        return None
    pre = t["state"] in lc.PRE_DISPATCH_STATES
    if not (status["status"] in ("AT RISK", "BREACHED") or (t["urgency"] >= 5 and pre)
            or t.get("reopen_count")):
        return None

    text = " ".join(t["evidence_list"] + [t["title"]]).lower()
    reasons = [f"Urgency score: {t['urgency']}/5 (SLA target {fmt_duration(status['target'])})"]

    sites = [s for s in SENSITIVE_SITES if re.search(rf"\b{re.escape(s)}\b", text)]
    if sites:
        reasons.append("Near " + ", ".join(sites))

    if status["status"] == "BREACHED":
        reasons.append(f"SLA breached {fmt_duration(-status['remaining'])} ago "
                       f"(unresolved for {fmt_duration(status['elapsed'])})")
    else:
        reasons.append(f"Report unresolved for {fmt_duration(status['elapsed'])} "
                       f"({status['pct']:.0%} of SLA window used)")

    hazard = re.search(HAZARD_RE, text)
    if "electr" in t["category"].lower() or hazard:
        reasons.append("Safety-critical infrastructure"
                       + (f" (keyword: “{hazard.group(0)}”)" if hazard else ""))

    dups = t["reports_count"] - 1
    if dups > 0:
        reasons.append(f"{dups} duplicate citizen report{'s' if dups != 1 else ''}")

    if t.get("reopen_count"):
        reasons.append(f"Citizen disputed the previous resolution: “{t['dispute_reason']}” "
                       f"(re-opened {t['reopen_count']}×)")
    if pre:
        reasons.append(f"No crew dispatched yet (status: {lc.STATE_LABELS[t['state']]})")
    if t["escalation_level"] > 0:
        reasons.append(f"Already escalated to {CHAIN_LABELS[CHAIN[t['escalation_level']]]}")

    notify = CHAIN[max(1, t["escalation_level"])]
    if pre:
        action = f"Immediate emergency dispatch of {t['team']}. {t['recommended_action']}"
    else:
        action = f"Get a status update from {t['team']} and add resources if needed."
    action += f" Notify {CHAIN_LABELS[notify]}."
    if t["escalation_level"] >= 2:
        action += " Supervisor to take command of the response."

    return {"complaint": t["title"], "reasons": reasons, "action": action,
            "escalate_to": CHAIN_LABELS[notify]}