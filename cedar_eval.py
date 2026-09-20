# cedar_eval.py
"""Dispatch authorization with the real Cedar engine (cedarpy).

Falls back to a Python mirror of policies.cedar if cedarpy is not installed
(pip install cedarpy).  authorize() returns a full explainable decision.
"""
import os
import re

try:
    import cedarpy
except ImportError:          # graceful fallback for demos
    cedarpy = None

POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policies.cedar")
FIELD_TECH_COST_LIMIT = 25000


def _load_policies():
    with open(POLICY_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    stripped = re.sub(r"//[^\n]*", "", text)
    meta = []
    for m in re.finditer(r"((?:@\w+\(\"[^\"]*\"\)\s*)*)(permit|forbid)\s*\(", stripped):
        ann = dict(re.findall(r'@(\w+)\("([^"]*)"\)', m.group(1)))
        meta.append({"id": ann.get("id", f"policy{len(meta)}"),
                     "reason": ann.get("reason", ""), "effect": m.group(2)})
    return text, meta


def _default_reason(role, t, action):
    if role == "Citizen":
        return "Citizens cannot dispatch crews."
    if role == "FieldTechnician":
        if t["category"] != "Electrical & Power":
            return f"No policy permits FieldTechnician to self-dispatch {t['category']} tickets."
        if t.get("cost", 0) > FIELD_TECH_COST_LIMIT:
            return (f"Dispatch cost Rs {t['cost']:,} exceeds the FieldTechnician "
                    f"limit of Rs {FIELD_TECH_COST_LIMIT:,}.")
    return f"No policy permits {role} to perform {action}."


def _mirror(role, t):
    """Python mirror of policies.cedar -> (allowed, policy_index)."""
    if role == "MunicipalOfficer":
        return True, 0
    if role == "Supervisor":
        return True, 1
    if role == "FieldTechnician":
        if t["urgency"] >= 4:
            return False, 2
        if t["urgency"] < 4 and t["category"] == "Electrical & Power" and t.get("cost", 0) <= FIELD_TECH_COST_LIMIT:
            return True, 3
    return False, None


def authorize(user_role: str, action: str, ticket: dict) -> dict:
    """ticket needs: ticket_id, category, urgency, cost."""
    text, meta = _load_policies()
    t = {"ticket_id": ticket["ticket_id"], "category": ticket["category"],
         "urgency": int(ticket["urgency"]), "cost": int(ticket.get("cost", 0))}

    if cedarpy is not None:
        entities = [
            {"uid": {"type": "User", "id": "session_user"}, "attrs": {},
             "parents": [{"type": "Role", "id": user_role}]},
            {"uid": {"type": "Role", "id": user_role}, "attrs": {}, "parents": []},
            {"uid": {"type": "Ticket", "id": t["ticket_id"]},
             "attrs": {"urgency": t["urgency"], "category": t["category"], "cost": t["cost"]},
             "parents": []},
        ]
        request = {"principal": 'User::"session_user"', "action": f'Action::"{action}"',
                   "resource": f'Ticket::"{t["ticket_id"]}"', "context": {}}
        resp = cedarpy.is_authorized(request, text, entities)
        allowed = bool(resp.allowed)
        idx = None
        for r in list(resp.diagnostics.reasons):
            m = re.fullmatch(r"policy(\d+)", str(r))
            if m and int(m.group(1)) < len(meta):
                idx = int(m.group(1))
        engine = "Cedar (cedarpy)"
    else:
        allowed, idx = _mirror(user_role, t)
        engine = "Python mirror of policies.cedar (install cedarpy for the real engine)"

    p = meta[idx] if idx is not None else None
    reason = (p["reason"] if p and p["reason"] else "") if p else _default_reason(user_role, t, action)
    return {
        "principal": user_role, "action": action, "resource": t["ticket_id"],
        "urgency": t["urgency"], "category": t["category"], "cost": t["cost"],
        "allowed": allowed, "decision": "ALLOW" if allowed else "DENY",
        "policy": p["id"] if p else "(default deny — no policy matched)",
        "reason": reason.replace(">=", "≥").replace("Rs ", "₹"), "engine": engine,
    }


def evaluate_ticket_action(user_role: str, action: str, ticket_data: dict) -> bool:
    """Backwards-compatible boolean wrapper."""
    return authorize(user_role, action, ticket_data)["allowed"]


if __name__ == "__main__":
    sample = {"ticket_id": "CF-1042", "category": "Electrical & Power", "urgency": 5, "cost": 80000}
    for r in ("FieldTechnician", "MunicipalOfficer", "Supervisor", "Citizen"):
        d = authorize(r, "ApproveDispatch", sample)
        print(f"{r:17} {d['decision']:5} {d['policy']} — {d['reason']}")