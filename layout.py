"""layout.py — design system (CSS), inline SVG icons, header, sidebar nav, time machine,
and a global fix for the "<div> shown as code" markdown bug."""
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import core
import lifecycle as lc
import sla_escalation as sla
import theme

ss = st.session_state

ROLES = ["Citizen", "FieldTechnician", "MunicipalOfficer", "Supervisor"]
ROLE_LABELS = {"Citizen": "Citizen", "FieldTechnician": "Field Technician",
               "MunicipalOfficer": "Municipal Officer", "Supervisor": "Supervisor"}
ICONS = {"Citizen": "🙋", "FieldTechnician": "🔧", "MunicipalOfficer": "👮", "Supervisor": "🏙️"}
DEMO_NAMES = {"Citizen": "Priya Singh", "FieldTechnician": "Ravi Kumar",
              "MunicipalOfficer": "Rajesh Verma", "Supervisor": "Anita Singh"}
HINTS = {"Citizen": "Search issues, wards, or ticket ID...",
         "Supervisor": "Search tickets, wards, departments...",
         "MunicipalOfficer": "Search tickets, wards, departments...",
         "FieldTechnician": "Search assigned tickets, wards..."}

# ------------------------------------------------------------------ icons (Lucide paths)
_P = {
    "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "map": '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "trending": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "sliders": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>',
    "ticket": '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
}
_ALIAS = {"◈": "map", "⚠": "alert", "⚠️": "alert", "▤": "layers", "✓": "check", "✅": "check", "✦": "zap",
          "↥": "trending", "◷": "clock", "⚙": "sliders", "🎫": "ticket", "👥": "users", "🔴": "alert",
          "🟠": "zap", "🟡": "clock", "🟢": "check", "⏳": "clock", "📋": "file", "🕑": "clock"}


def svg(name, size=20):
    key = _ALIAS.get(name, name)
    if key not in _P:
        return name
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{_P[key]}</svg>')


def stat_card(icon, value, label, color="blue", extra=""):
    """KPI card (86px, 52px icon box). Also replaces theme.stat_card so the citizen page matches."""
    bg, fg = theme.STAT_COLORS.get(color, theme.STAT_COLORS["blue"])
    ex = f'<div class="cf-stat-extra">{extra}</div>' if extra else ""
    return (f'<div class="cf-stat-card"><div class="cf-stat-icon" style="background:{bg};color:{fg};">{svg(icon, 26)}</div>'
            f'<div><div class="cf-stat-value">{value}</div><div class="cf-stat-label">{label}</div>{ex}</div></div>')


# ------------------------------------------------------------------ markdown bug fix
def _flat(s):
    """Drop blank/whitespace-only lines and indentation so Markdown never ends an HTML block early
    (that was what turned '</div>' and whole summaries into code blocks)."""
    if "<" not in s:
        return s
    return "\n".join(l.lstrip() for l in s.splitlines() if l.strip())


def _patch_markdown():
    if getattr(st, "_cf_md_patched", False):
        return
    orig_method = DeltaGenerator.markdown
    orig_main = st.markdown

    def _prep(body, a, k):
        unsafe = k.get("unsafe_allow_html", a[0] if a else False)
        return _flat(body) if unsafe and isinstance(body, str) else body

    def dg_markdown(self, body, *a, **k):
        return orig_method(self, _prep(body, a, k), *a, **k)

    def st_markdown(body, *a, **k):
        return orig_main(_prep(body, a, k), *a, **k)

    DeltaGenerator.markdown = dg_markdown
    st.markdown = st_markdown
    st._cf_md_patched = True


# ------------------------------------------------------------------ CSS (from the design spec)
CSS = """
<style>
html, body, [class*="css"], .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
[data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main, .stApp {
    background: linear-gradient(135deg,#F8FBFF 0%,#F3F8FF 50%,#F8FCFF 100%) !important; }
[data-testid="stHeader"] { height:0 !important; min-height:0 !important; background:transparent !important; }
[data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }
.block-container { padding:0 24px 20px 28px !important; max-width:100% !important; }
[data-testid="stVerticalBlock"] { gap:.5rem !important; }
[data-testid="stHorizontalBlock"] { gap:10px !important; }
div[data-testid="stElementContainer"]:has(.cf-marker):not(:has([data-testid="stVerticalBlock"])),
.element-container:has(.cf-marker):not(:has([data-testid="stVerticalBlock"])) { display:none !important; }

/* ---- type scale ---- */
[data-testid="stMarkdownContainer"] p { font-size:13.5px; line-height:1.45; margin:0 0 .25rem; }
h3 { font-size:20px !important; font-weight:700 !important; color:#101B55; padding:0 !important; margin:0 0 .5rem 0 !important; }
h4 { font-size:17px !important; font-weight:650 !important; color:#101B55; padding:0 !important; margin:0 0 .45rem 0 !important; }
h5 { font-size:15px !important; font-weight:650 !important; color:#101B55; padding:0 !important; margin:0 0 .5rem 0 !important; }
[data-testid="stCaptionContainer"] { font-size:12px; }

/* ---- sidebar (258px, fixed) ---- */
section[data-testid="stSidebar"][aria-expanded="true"] { width:258px !important; min-width:258px !important; }
section[data-testid="stSidebar"] { background:#F3F8FE !important; border-right:1px solid #E1EAF5 !important; }
[data-testid="stSidebarHeader"] { display:none !important; }
[data-testid="stSidebarUserContent"] { padding:0 14px 10px !important; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:6px !important; }
.cf-brand { display:flex; align-items:center; gap:11px; padding:24px 6px 14px 6px; }
.cf-brand-icon { width:48px; height:48px; border-radius:12px; font-size:24px; }
.cf-brand-title { font-size:29px; font-weight:750; color:#101B55; line-height:1.05; }
.cf-brand-sub { font-size:13px; line-height:18px; color:#405889; margin-top:2px; }
.cf-side-menu-label { font-size:10.5px; letter-spacing:.12em; color:#94A3B8; font-weight:700; margin:16px 0 10px 6px; }
section[data-testid="stSidebar"] .stButton > button {
    height:44px !important; min-height:44px !important; border-radius:8px !important; padding:0 12px 0 16px !important;
    font-size:15px !important; line-height:20px !important; font-weight:500 !important; margin:0 !important;
    justify-content:flex-start !important; transition:background .15s ease; }
section[data-testid="stSidebar"] .stButton > button p { font-size:15px !important; margin:0 !important; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
    background:#1683F7 !important; color:#fff !important; box-shadow:0 3px 8px rgba(22,131,247,.18) !important; }
body:has(.cf-role-supervisor) section[data-testid="stSidebar"] .stButton > button[kind="primary"],
body:has(.cf-role-supervisor) section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
    background:#6348E8 !important; box-shadow:0 3px 8px rgba(99,72,232,.22) !important; }
.cf-side-foot { margin-top:18px; margin-bottom:14px; padding:0 4px; }
.cf-side-foot .msg { display:flex; align-items:center; gap:10px; color:#304A7A; font-size:15px; line-height:21px; margin-top:6px; }
.cf-side-foot .msg svg { color:#16A34A; flex-shrink:0; }

/* ---- header (68px bar, bleeds to the edges of the main area) ---- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) {
    height:68px; min-height:68px; display:flex; align-items:center; background:#EEF5FF !important;
    border:none !important; border-bottom:1px solid #E0EAF5 !important; border-radius:0 !important;
    box-shadow:none !important; padding:0 28px !important; margin:0 -24px 17px -28px; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) > div { width:100%; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) [data-testid="stHorizontalBlock"] { align-items:center; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr):hover { transform:none !important; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) [data-testid="stTextInput"] { max-width:500px; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) input {
    height:40px; border-radius:20px; background:#fff !important; border:1px solid #E5EDF7; font-size:14px;
    box-shadow:0 1px 5px rgba(40,80,130,.05); padding-left:16px; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) input::placeholder { color:#7185A8; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) [data-testid="stPopover"] > button {
    background:transparent; border:1px solid transparent; box-shadow:none; height:40px; font-size:14px; color:#304A7A; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) [data-testid="stPopover"] > button:hover { background:#fff; }
.cf-loc-txt { font-size:14px; color:#405889; white-space:nowrap; }
.cf-hdr-user { display:flex; align-items:center; gap:12px; justify-content:flex-end; }
.cf-hdr-user .av { width:44px; height:44px; border-radius:50%; color:#fff; font-weight:700; font-size:15px;
    display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,#2563EB,#3B82F6); }
.cf-role-supervisor-av { background:linear-gradient(135deg,#6952D9,#805EEA) !important; }
.cf-hdr-user .nm { font-size:15px; font-weight:600; color:#101B55; line-height:1.15; }
.cf-hdr-user .rl { font-size:12px; color:#64748B; margin-top:1px; }

/* ---- cards ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background:#fff; border:1px solid #E1EBF5 !important; border-radius:11px !important; padding:12px 14px !important;
    box-shadow:0 2px 9px rgba(40,80,130,.07); transition:transform .15s ease, box-shadow .15s ease;
    margin-bottom:16px !important; }
div[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow:0 4px 14px rgba(40,80,130,.10); }
/* the sticky 68px header bar must keep its own tight margin, not the generic card gap above */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cf-marker-hdr) { margin:0 -24px 17px -28px !important; }

/* Every row of side-by-side cards gets consistent breathing room above and below it,
   so a card row never visually touches the section title/heading that follows
   (this was the "Report an Issue / Issue Map / Common Issues" collision). */
[data-testid="stHorizontalBlock"] { margin:6px 0 18px 0 !important; }

/* ---- equal-height cards within a row ----
   Streamlit sizes each card to its own content, so two cards side by side with
   different amounts of content end at different heights and the row looks ragged.
   The row itself is a flex container (align-items:stretch below), so every
   column is already stretched to the tallest column's height; what's missing is
   getting each column's *own* cards to actually fill that stretched height.
   For a column that holds a single card (the common "row of dashboard cards"
   case) we stretch that one card to 100%. For a column that stacks several
   cards (e.g. the citizen home page's "Common Issues / Need Urgent Help /
   Civic Awareness" column), stretching every card to 100% would make them
   overlap — so only the LAST card in a multi-card column grows to soak up the
   remaining space, while the earlier cards keep their natural height. Either
   way, every column in the row now ends at the same y-coordinate, and the
   normal card margin-bottom above keeps a clean gap before whatever comes
   next on the page.
   The fixed-height header bar above (:has(.cf-marker-hdr), set with !important)
   is more specific than these rules and is unaffected. */
[data-testid="stHorizontalBlock"] { align-items: stretch; }
[data-testid="stHorizontalBlock"] > div { display: flex; flex-direction: column; }
[data-testid="stHorizontalBlock"] > div > div {
    display: flex; flex-direction: column; flex: 1 1 auto; }
[data-testid="stHorizontalBlock"] > div div[data-testid="stVerticalBlock"] { height: 100%; }
[data-testid="stHorizontalBlock"] > div div[data-testid="stVerticalBlockBorderWrapper"] {
    flex: 0 0 auto; }
[data-testid="stHorizontalBlock"] > div div[data-testid="stVerticalBlockBorderWrapper"]:last-of-type {
    flex: 1 1 auto; display: flex; flex-direction: column; }
[data-testid="stHorizontalBlock"] > div div[data-testid="stVerticalBlockBorderWrapper"]:last-of-type > div {
    flex: 1 1 auto; display: flex; flex-direction: column; height: 100%; }
.cf-sup-card-head { padding:0 0 10px !important; margin-bottom:6px; font-size:16px !important; }
.cf-sup-card-head b { font-weight:650; }
.cf-section-icon { width:24px !important; height:24px !important; }
.cf-hotspot-title { padding:2px 0 4px !important; font-size:15px; }
.cf-hotspot-count, .cf-severity { padding-left:0 !important; padding-right:0 !important; }

/* ---- KPI cards ---- */
.cf-stat-card { height:86px; padding:13px 14px; gap:13px; border-radius:11px; border:1px solid #E1EBF5;
    box-shadow:0 2px 9px rgba(40,80,130,.07); transition:transform .15s ease, box-shadow .15s ease; }
.cf-stat-card:hover { transform:translateY(-1px); box-shadow:0 4px 14px rgba(40,80,130,.10); }
.cf-stat-icon { width:52px; height:52px; border-radius:12px; }
.cf-stat-value { font-size:26px; line-height:28px; font-weight:700; color:#101B55; }
.cf-stat-label { font-size:12.5px; line-height:18px; margin-top:2px; }
.cf-stat-extra { font-size:11px; }

/* ---- welcome ---- */
.cf-sup-welcome, .cf-welcome-row { background:transparent !important; border:none !important; padding:0 !important;
    margin:0 0 14px 0 !important; align-items:flex-start; }
.cf-sup-greeting, .cf-welcome-title { font-size:34px !important; line-height:40px !important; font-weight:750 !important; color:#101B55 !important; }
.cf-sup-subtitle, .cf-welcome-sub { font-size:15px !important; line-height:21px !important; color:#405889 !important; margin-top:6px !important; }
.cf-sup-quote, .cf-welcome-quote { background:transparent !important; border:none !important; font-size:17px !important;
    line-height:22px !important; font-style:italic; color:#304A7A !important; text-align:right; min-width:0 !important; max-width:230px; padding:0 !important; }

/* ---- buttons / tabs / pills ---- */
.stButton > button, .stDownloadButton > button { min-height:34px; padding:0 13px; border-radius:7px; font-size:12px; transition:background .15s ease; }
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] { min-height:40px; font-size:14px; font-weight:600; }
button[data-baseweb="tab"] { height:42px; font-size:14px; }
.cf-pill { height:24px; line-height:18px; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:500; }
div[data-testid="stMetric"] { padding:8px 12px; border-radius:11px; border:1px solid #E1EBF5; }
div[data-testid="stMetricValue"] { font-size:1.5rem; font-weight:700; }
div[data-testid="stMetricLabel"] { font-size:12px; font-weight:500; }
</style>
"""


def inject():
    _patch_markdown()
    theme.stat_card = stat_card
    st.markdown(CSS, unsafe_allow_html=True)


def marker(cls=""):
    st.markdown(f'<span class="cf-marker {cls}"></span>', unsafe_allow_html=True)


# ------------------------------------------------------------------ navigation
MATERIAL = {"Home": "home", "Report an Issue": "add_circle", "My Complaints": "description", "Track Status": "explore",
            "Map & Hotspots": "map", "Give Feedback": "chat", "Community": "group", "Help & Support": "help",
            "Dashboard": "dashboard", "All Tickets": "confirmation_number", "Escalations": "warning",
            "Team Management": "groups", "Ward Analytics": "bar_chart", "City Map & Hotspots": "map",
            "Approvals": "task_alt", "Reports": "assessment", "Policy & Authorization": "policy",
            "Notifications": "notifications", "Ticket Center": "confirmation_number", "Analytics": "bar_chart",
            "Registry & Audit": "history", "My Crew Queue": "engineering", "Map": "map"}

SKYLINE = ('<svg viewBox="0 0 230 110" width="100%" height="110" xmlns="http://www.w3.org/2000/svg">'
           '<rect x="30" y="40" width="26" height="70" rx="2" fill="#D6E6FA"/><rect x="62" y="18" width="34" height="92" rx="2" fill="#C3DAF6"/>'
           '<rect x="102" y="52" width="28" height="58" rx="2" fill="#D6E6FA"/><rect x="136" y="30" width="30" height="80" rx="2" fill="#CADDF7"/>'
           '<circle cx="18" cy="88" r="18" fill="#7BC98F"/><rect x="16" y="98" width="4" height="12" fill="#5B8F6B"/>'
           '<circle cx="196" cy="84" r="20" fill="#6DBE83"/><rect x="194" y="96" width="4" height="14" fill="#5B8F6B"/>'
           '<path d="M0 110 Q60 92 120 104 T230 100 V110Z" fill="#B7E4C7"/></svg>')


def page_key(role):
    return "citizen_page" if role == "Citizen" else f"page_{role}"


def goto(page):
    role = ss.get("actor_role", "Citizen")
    ss[page_key(role)] = page
    ss[f"search_{role}"] = ""


def _nav_button(label, key, active, name, emoji):
    kw = dict(key=key, use_container_width=True, type="primary" if active else "secondary")
    try:
        return st.sidebar.button(label, icon=f":material/{MATERIAL.get(name, 'circle')}:", **kw)
    except Exception:       # older Streamlit without button icons
        return st.sidebar.button(f"{emoji}  {label}", **kw)


def sidebar_nav(role, pages, badges=None):
    badges = badges or {}
    key = page_key(role)
    ss.setdefault(key, pages[0][0])
    st.sidebar.markdown('<div class="cf-side-menu-label">MENU</div>', unsafe_allow_html=True)
    for name, emoji in pages:
        n = badges.get(name)
        label = name + (f"  ({n})" if n else "")
        if _nav_button(label, f"nav_{role}_{name}", ss[key] == name, name, emoji):
            goto(name)
            st.rerun()
    tag = "Your Voice<br>A Better Tomorrow" if role == "Citizen" else "Lead Today<br>for a Better Tomorrow"
    st.sidebar.markdown(f'<div class="cf-side-foot">{SKYLINE}<div class="msg">{svg("leaf", 30)}<span>{tag}</span></div></div>',
                        unsafe_allow_html=True)


def _bump(m):
    ss["clock_offset_min"] = ss.get("clock_offset_min", 0) + m


def _reset():
    ss["clock_offset_min"] = 0


def time_machine():
    with st.sidebar.expander("⏱️ Time machine (demo)"):
        st.caption("Fast-forward the clock to watch SLAs breach, tickets escalate and hotspots shift.")
        a, b, c = st.columns(3)
        a.button("+10m", key="tm10", on_click=_bump, args=(10,))
        b.button("+30m", key="tm30", on_click=_bump, args=(30,))
        c.button("+2h", key="tm120", on_click=_bump, args=(120,))
        st.button("Reset clock", key="tm_reset", on_click=_reset)
        st.caption(f"Simulated time: **{core.now():%d %b, %H:%M}** (+{ss.get('clock_offset_min', 0)} min)")


# ------------------------------------------------------------------ notifications + header
def notifications(role, NOW, limit=8):
    items = [f"📣 {b}" for b in ss.get("broadcasts", [])[-3:][::-1]]
    for t in core.tickets().values():
        if role == "Citizen":
            if "me" not in t["reporters"]:
                continue
            if t["state"] == "RESOLVED":
                items.append(f"✅ {t['ticket_id']} was resolved — please confirm the fix")
            elif t["state"] == "IN PROGRESS":
                items.append(f"🛠️ {t['ticket_id']}: crew is working on it")
            continue
        if not lc.is_active(t):
            continue
        if role == "FieldTechnician" and t["state"] not in ("ASSIGNED", "IN PROGRESS"):
            continue
        s = sla.sla_status(t, NOW)
        if s["status"] == "BREACHED":
            items.append(f"🚨 {t['ticket_id']} SLA breached {sla.fmt_duration(-s['remaining'])} ago")
        elif s["status"] == "AT RISK":
            items.append(f"⚠️ {t['ticket_id']} SLA breach in {sla.fmt_duration(s['remaining'])}")
    return items[:limit]


def _popover(col, label, icon, fallback):
    try:
        return col.popover(label, icon=f":material/{icon}:", use_container_width=True)
    except Exception:
        return col.popover(f"{fallback} {label}".strip(), use_container_width=True)


def header(role, NOW):
    name = DEMO_NAMES[role]
    notes = notifications(role, NOW)
    av_cls = "av cf-role-supervisor-av" if role == "Supervisor" else "av"
    with st.container(border=True):
        marker("cf-marker-hdr")
        c1, c2, c3, c4, c5 = st.columns([4.6, 1.6, 0.75, 2.3, 1.1])
        c1.text_input("Search", key=f"search_{role}", placeholder=HINTS[role], label_visibility="collapsed")
        c2.markdown('<div class="cf-loc-txt">📍 Dayalpur, Patna</div>', unsafe_allow_html=True)
        with _popover(c3, str(len(notes)) if notes else "", "notifications", "🔔"):
            st.markdown("**Notifications**")
            if not notes:
                st.caption("You're all caught up 🎉")
            for n in notes:
                st.markdown(f"- {n}")
        c4.markdown(f'<div class="cf-hdr-user"><div class="{av_cls}">{theme.initials(name)}</div>'
                    f'<div><div class="nm">{name}</div><div class="rl">{ROLE_LABELS[role]}</div></div></div>',
                    unsafe_allow_html=True)
        with _popover(c5, "Switch", "swap_horiz", "🔁"):
            st.caption("Switch user")
            st.radio("Sign in as", ROLES, key="actor_role", label_visibility="collapsed",
                     format_func=lambda r: f"{ICONS[r]} {ROLE_LABELS[r]} — {DEMO_NAMES[r]}")