import streamlit as st

st.set_page_config(page_title="CivicFlow — Grievance Triage Agent", page_icon="🏛️", layout="wide")

import core
import layout
import sla_escalation as sla
import staff_ui
import theme
import views

theme.inject()
layout.inject()

ss = st.session_state
ss.setdefault("clock_offset_min", 0)
ss.setdefault("actor_role", "Citizen")     # switched from the header user menu
core.init_state()

role = ss["actor_role"]
ss["actor_name"] = layout.DEMO_NAMES[role]
NOW = core.now()

# ---------------------------------------------------------------- sidebar
theme.brand_block()
st.sidebar.caption("AWS Strands · Ollama · Cedar · LocalStack")
if role == "Citizen":
    layout.sidebar_nav(role, [(p, views.CITIZEN_ICONS[p]) for p in views.CITIZEN_PAGES])
else:
    layout.sidebar_nav(role, staff_ui.PAGES[role], staff_ui.badges(role, NOW))
layout.time_machine()

# ------------------------------------- automatic SLA escalation (every rerun)
for esc_ticket, to_role, _note in sla.apply_escalations(core.tickets(), NOW):
    core.log_event(esc_ticket, "SLA Engine", f"Auto-escalated to {to_role}", "ESCALATED")

# ----------------------------------------------------------------- header
layout.header(role, NOW)

# ------------------------------------------------------------------- body
query = ss.get(f"search_{role}", "").strip()
if query:
    staff_ui.render_search(role, query, NOW)
elif role == "Citizen":
    views.render_citizen(NOW)
else:
    staff_ui.render(role, NOW)