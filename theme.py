"""Professional visual theme for CivicFlow (Streamlit).

Injected once from app.py. Everything here is CSS/HTML only — no behaviour
changes — so it layers on top of the existing feature set without touching
any logic.

v2: light "SaaS dashboard" theme (white sidebar, light topbar with search,
stat cards, pill badges) to match the citizen-app reference design, applied
consistently across Citizen / Field Technician / Municipal Officer /
Supervisor screens.
"""
import streamlit as st

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

/* ---------- App background ---------- */
[data-testid="stAppViewContainer"] > .main { background: #EEF2F9; }
.block-container { padding-top: 1.4rem; }

/* ---------- Sidebar (light) ---------- */
section[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}
section[data-testid="stSidebar"] * { color: #1E293B !important; }
section[data-testid="stSidebar"] hr { border-color: #E5E7EB; margin: 10px 0; }
section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {
    color: #94A3B8 !important; letter-spacing: .04em;
}
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
    background-color: #F8FAFC; color: #0F172A !important; border-radius: 8px;
    border: 1px solid #E2E8F0;
}
section[data-testid="stSidebar"] .stButton>button {
    background: transparent !important;
    border: 1px solid transparent !important;
    color: #334155 !important;
    border-radius: 10px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-weight: 600 !important;
    padding: 0.5rem 0.8rem !important;
}
section[data-testid="stSidebar"] .stButton>button:hover {
    background: #F1F5F9 !important;
    border-color: #E2E8F0 !important;
}
section[data-testid="stSidebar"] .stButton>button[kind="primary"] {
    background: #2563EB !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 6px rgba(37,99,235,0.25);
}

/* ---------- Buttons (main area) ---------- */
.stButton>button {
    border-radius: 10px;
    font-weight: 600;
    padding: 0.45rem 1rem;
}
.stButton>button[kind="primary"] {
    background: linear-gradient(90deg,#2563EB,#3B82F6);
    border: none;
    color: #fff;
    box-shadow: 0 2px 6px rgba(37,99,235,0.30);
}

/* ---------- Cards / bordered containers ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid #E5E7EB !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06);
    background: #FFFFFF;
}

/* ---------- Metrics ---------- */
div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
div[data-testid="stMetricValue"] { font-weight: 800; color:#0F172A; }
div[data-testid="stMetricLabel"] { font-weight: 600; color:#64748B; }

/* ---------- Tabs ---------- */
button[data-baseweb="tab"] { font-weight: 600; }

/* ---------- Dataframes ---------- */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ---------- Expanders ---------- */
details {
    border-radius: 12px !important;
    border: 1px solid #E5E7EB !important;
    background: #FFFFFF;
}

/* ---------- Sidebar brand block ---------- */
.cf-brand { display:flex; align-items:center; gap:10px; padding:4px 2px 14px 2px; }
.cf-brand-icon {
    width:40px; height:40px; border-radius:12px; background:#0F172A; color:#fff;
    display:flex; align-items:center; justify-content:center; font-size:19px; flex-shrink:0;
}
.cf-brand-title { font-size:17px; font-weight:800; color:#0F172A; line-height:1.1; }
.cf-brand-sub { font-size:10.5px; color:#64748B; line-height:1.25; margin-top:2px; }

/* ---------- Top bar (staff — icon + title) ---------- */
.cf-topbar {
    display:flex; align-items:center; justify-content:space-between;
    padding:14px 22px; border-radius:16px; margin-bottom:20px;
    background: #FFFFFF; border:1px solid #E5E7EB;
    box-shadow: 0 2px 8px rgba(15,23,42,0.05);
    gap: 16px; flex-wrap: wrap;
}
.cf-topbar-left { display:flex; align-items:center; gap:14px; }
.cf-topbar-logo {
    width:42px; height:42px; border-radius:12px;
    background: #EFF6FF; color:#2563EB;
    display:flex; align-items:center; justify-content:center; font-size:21px;
}
.cf-topbar h1 { margin:0; font-size:18px; color:#0F172A; font-weight:800; }
.cf-topbar .cf-sub { font-size:12.5px; color:#64748B; margin-top:2px; }
.cf-topbar-right { display:flex; align-items:center; gap:16px; flex-wrap: wrap; }

/* ---------- Top bar (citizen — search bar) ---------- */
.cf-topbar-light { justify-content: space-between; }
.cf-search {
    display:flex; align-items:center; gap:10px;
    background:#F1F5F9; border-radius:12px; padding:10px 16px;
    color:#94A3B8; font-size:13.5px; flex:1; max-width:440px; min-width: 200px;
}
.cf-search-placeholder { color:#94A3B8; }

.cf-loc, .cf-loc-light { font-size:12.5px; color:#475569; white-space:nowrap; }
.cf-bell, .cf-bell-light { font-size:18px; color:#475569; position:relative; }
.cf-badge {
    position:absolute; top:-6px; right:-9px; background:#EF4444; color:#fff;
    border-radius:999px; font-size:10px; font-weight:700; padding:1px 5px; line-height:1.3;
}
.cf-avatar {
    width:38px; height:38px; border-radius:50%;
    background: linear-gradient(135deg,#4F46E5,#6366F1); color:white;
    display:flex; align-items:center; justify-content:center;
    font-weight:700; font-size:14px; flex-shrink:0;
}
.cf-user, .cf-user-light { display:flex; flex-direction:column; line-height:1.2; white-space:nowrap; }
.cf-user b, .cf-user-light b { color:#0F172A; font-size:13px; }
.cf-user span, .cf-user-light span { color:#64748B; font-size:11px; }
.cf-chevron { color:#94A3B8; font-size:12px; }

/* ---------- Badges / pills ---------- */
.cf-pill {
    display:inline-block; padding:3px 11px; border-radius:999px;
    font-size:12px; font-weight:700;
}
.cf-pill-red    { background:#FEE2E2; color:#B91C1C; }
.cf-pill-orange { background:#FFEDD5; color:#C2410C; }
.cf-pill-yellow { background:#FEF9C3; color:#A16207; }
.cf-pill-green  { background:#DCFCE7; color:#166534; }
.cf-pill-blue   { background:#DBEAFE; color:#1D4ED8; }
.cf-pill-grey   { background:#F3F4F6; color:#4B5563; }

/* ---------- AI callout cards ---------- */
.cf-ai-card {
    border-radius:14px; padding:16px 18px; margin:8px 0;
    background: linear-gradient(135deg,#EEF2FF 0%, #F5F3FF 100%);
    border: 1px solid #E0E7FF;
}
.cf-ai-card h4 { margin:0 0 8px 0; color:#3730A3; font-size:14.5px; }
.cf-ai-card .cf-row { font-size:13.5px; color:#1F2937; margin:3px 0; }
.cf-ai-card .cf-row b { color:#111827; }

.cf-brief-card {
    border-radius:14px; padding:16px 18px; margin:10px 0;
    background:#FFFFFF; border:1px solid #E5E7EB; border-left:6px solid #6366F1;
    box-shadow:0 1px 3px rgba(15,23,42,0.06);
}

/* ---------- Citizen: welcome banner ---------- */
.cf-welcome-row {
    display:flex; align-items:center; justify-content:space-between; gap: 20px;
    background: linear-gradient(90deg,#EFF6FF,#F5F3FF);
    border:1px solid #E0E7FF; border-radius:16px; padding:20px 26px; margin-bottom:18px;
    flex-wrap: wrap;
}
.cf-welcome-title { font-size:23px; font-weight:800; color:#0F172A; }
.cf-welcome-sub { font-size:13.5px; color:#475569; margin-top:4px; max-width: 560px; }
.cf-welcome-quote { font-size:13px; color:#4B5563; font-style:italic; text-align:right; max-width:220px; }

/* ---------- Citizen: stat cards ---------- */
.cf-stat-card {
    display:flex; align-items:center; gap:12px;
    background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:14px 16px;
    box-shadow:0 1px 2px rgba(15,23,42,0.04); height: 100%;
}
.cf-stat-icon {
    width:44px; height:44px; border-radius:12px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:20px;
}
.cf-stat-value { font-size:22px; font-weight:800; color:#0F172A; line-height:1.15; }
.cf-stat-label { font-size:12.5px; color:#64748B; font-weight:600; }
.cf-stat-extra { font-size:11.5px; color:#16A34A; font-weight:700; margin-top:2px; }
.cf-thanks-card {
    background:#ECFDF5; border:1px solid #BBF7D0; border-radius:14px; padding:14px 16px;
    font-size:13px; color:#166534; height:100%;
}
.cf-thanks-card span { display:block; font-weight:500; font-size:12px; color:#166534; margin-top:2px; }

/* ---------- Citizen: help / awareness side cards ---------- */
.cf-help-card {
    border-radius:14px; padding:16px 18px; margin: 10px 0;
    background:#FEF2F2; border:1px solid #FECACA;
}
.cf-help-card b { color:#B91C1C; font-size:14px; }
.cf-help-card p { margin:4px 0 0 0; font-size:12.5px; color:#7F1D1D; }

.cf-eco-card {
    border-radius:14px; padding:16px 18px; margin: 10px 0;
    background:#ECFDF5; border:1px solid #BBF7D0;
}
.cf-eco-card b { color:#166534; font-size:14px; }
.cf-eco-card p { margin:4px 0 0 0; font-size:12.5px; color:#166534; }

/* ---------- Supervisor command-center theme ---------- */
.cf-sup-welcome{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 2px 8px;padding:0 4px;}
.cf-sup-greeting{font-size:25px;line-height:1.08;color:#111B5B;font-weight:800;}
.cf-sup-subtitle{font-size:12.5px;color:#3F568D;margin-top:3px;}
.cf-sup-quote{background:linear-gradient(135deg,#F0EDFF,#E9E4FF);border:1px solid #E3DCFF;border-radius:10px;padding:9px 14px;color:#373078;font-size:12px;font-style:italic;min-width:270px;text-align:center;}
.cf-sup-stat{display:flex;align-items:center;gap:9px;background:#fff;border:1px solid #E3E8F2;border-radius:10px;padding:8px 10px;min-height:58px;box-shadow:0 2px 7px rgba(31,53,95,.05);}
.cf-sup-stat-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;}
.cf-sup-stat-value{font-size:19px;font-weight:800;color:#101A54;line-height:1.0;}
.cf-sup-stat-label{font-size:10.5px;color:#4A5C88;margin-top:3px;white-space:nowrap;}
.cf-sup-trend{font-size:10px;font-weight:800;margin-top:2px;}
.cf-sup-section-gap{height:6px;}
.cf-sup-card{background:#fff;border:1px solid #E1E7F1;border-radius:10px;box-shadow:0 2px 8px rgba(30,52,92,.05);overflow:hidden;}
.cf-sup-card-head{display:flex;align-items:center;justify-content:space-between;gap:7px;padding:9px 11px;border-bottom:1px solid #EDF1F7;color:#101A54;font-size:13px;}
.cf-sup-card-head>div{display:flex;align-items:center;gap:8px;}
.cf-view-all{font-size:11px;color:#2563EB;font-weight:600;white-space:nowrap;}
.cf-section-icon{width:22px;height:22px;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;font-size:15px;font-weight:800;}
.cf-section-icon.blue{background:#E6F0FF;color:#2563EB}.cf-section-icon.red{background:#FEE8EB;color:#EF3340}.cf-section-icon.orange{background:#FFF2DC;color:#E88A00}.cf-section-icon.green{background:#E2F8EC;color:#12A45A}.cf-section-icon.purple{background:#EEE9FF;color:#6D4AEF}.cf-section-icon.navy{background:#E7ECF7;color:#334A86}
.cf-map-legend{display:flex;align-items:center;gap:8px;font-size:10px;color:#53658D;font-weight:600;flex-wrap:wrap;}
.cf-map-legend .active{background:#6348E8;color:#fff;border-radius:6px;padding:4px 8px;}
.cf-filter{font-size:10px;color:#354B7D;border:1px solid #E0E6F0;border-radius:7px;padding:6px 9px;white-space:nowrap;}
.cf-heatmap-card .cf-geo-section{padding:0!important;margin:0!important;}
.cf-hotspot-side{padding-bottom:13px;}
.cf-hotspot-title{padding:11px 12px 5px;color:#152052;font-size:15px;}
.cf-hotspot-count{display:flex;justify-content:space-between;padding:6px 12px 8px;color:#71809F;font-size:12px;border-bottom:1px solid #EDF1F7;}
.cf-hotspot-count b{color:#152052;font-size:12px;}
.cf-severity{display:flex;justify-content:space-between;padding:6px 12px;font-size:12px;color:#25345E;}
.cf-severity b{color:#17204E;}
.cf-bar-row{display:grid;grid-template-columns:1.35fr 1.8fr .35fr;align-items:center;gap:7px;padding:5px 11px;font-size:11.5px;color:#26375F;}
.cf-bar{height:10px;border-radius:8px;background:#EAF0F8;overflow:hidden;}.cf-bar i{display:block;height:100%;border-radius:8px;}.cf-bar i.pink{background:#D83C76}.cf-bar i.blue{background:#4897F2}.cf-bar i.yellow{background:#F1BF55}.cf-bar i.green{background:#48C19A}.cf-bar i.purple{background:#7451D9}
.cf-sla-body{display:flex;align-items:center;gap:12px;padding:10px 10px;}
.cf-donut{width:82px;height:82px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:conic-gradient(#18B96D 0 var(--pct),#FF9E19 var(--pct) calc(var(--pct) + 32deg),#F0F3F8 calc(var(--pct) + 32deg) 360deg);position:relative;flex-shrink:0;}
.cf-donut:after{content:"";position:absolute;width:58px;height:58px;border-radius:50%;background:#fff;}.cf-donut>div{position:relative;z-index:1;text-align:center}.cf-donut b{display:block;font-size:17px;color:#17204E}.cf-donut span{font-size:10px;color:#71809F}.cf-sla-legend{flex:1;font-size:11px;color:#31436F}.cf-sla-legend div{display:flex;align-items:center;gap:6px;margin:6px 0}.cf-sla-legend i{width:10px;height:10px;border-radius:50%;display:inline-block}.cf-sla-legend i.green{background:#18B96D}.cf-sla-legend i.orange{background:#FF9E19}.cf-sla-legend i.red{background:#F0334A}.cf-sla-legend b{margin-left:auto;color:#17204E}
.cf-ai-brief{background:linear-gradient(180deg,#fff,#FBFAFF);}.cf-ai-line{display:flex;gap:6px;padding:6px 10px;border-bottom:1px solid #F0F1F6;align-items:flex-start}.cf-ai-line:last-child{border-bottom:0}.cf-ai-line span{width:19px;height:19px;border-radius:50%;background:#F2A52A;color:#fff;font-size:11px;display:flex;align-items:center;justify-content:center;font-weight:800;flex-shrink:0}.cf-ai-line p{margin:0;font-size:11.5px;line-height:1.35;color:#33446D}.cf-ai-note{padding-bottom:10px;background:#FFFDF2;}.cf-ai-note-row{display:flex;gap:8px;padding:7px 12px;font-size:11.5px;color:#34436A}.cf-ai-note-row b{width:19px;height:19px;border-radius:50%;background:#D98723;color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.cf-critical-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 10px;border-bottom:1px solid #EDF1F7;}.cf-critical-row:last-child{border-bottom:0}.cf-critical-main{min-width:0;flex:1;font-size:11.5px;color:#27385F}.cf-critical-title{font-size:11px;color:#182653;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cf-critical-meta{font-size:9.5px;color:#7B88A3;margin-top:2px}.cf-critical-status{float:right;color:#EF3340;font-size:10.5px;font-weight:700}.cf-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 4px}.cf-dot.red{background:#EF3340}.cf-dot.orange{background:#F28A16}.cf-fake-action{border:1px solid #CFE0FA;background:#F5F9FF;color:#1769D0;border-radius:7px;padding:5px 8px;font-size:9.5px;font-weight:600;white-space:nowrap;}
.cf-table-card .stDataFrame{padding:0 8px 8px}.cf-activity-card{padding-bottom:8px}.cf-activity-row{display:flex;align-items:center;gap:6px;padding:6px 10px;font-size:11px;color:#33446D}.cf-activity-time{width:34px;color:#71809F;font-weight:700}.cf-activity-dot{width:7px;height:7px;border-radius:50%;background:#4A4B9A;box-shadow:0 0 0 3px #E9E9F8;}
.cf-quick-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:7px}.cf-quick-btn{min-height:43px;border-radius:9px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;font-size:17px}.cf-quick-btn span{font-size:10px}.cf-quick-btn.green{background:#E9F8F1;color:#10A764}.cf-quick-btn.purple{background:#F0EBFF;color:#6B4AD8}.cf-quick-btn.blue{background:#EAF3FF;color:#2B73D9}.cf-quick-btn.orange{background:#FFF2E0;color:#F08A0C}
.cf-supervisor-topbar{height:58px!important;}
.cf-supervisor-topbar + *{margin-top:0!important;}
.cf-sup-card .stDataFrame{margin:0!important;}
.cf-sup-card .stButton{margin:3px 8px 6px!important;}
.cf-sup-card .stButton>button{min-height:30px!important;height:30px!important;padding:2px 8px!important;font-size:10px!important;}
.cf-sup-card .stMarkdown{margin-bottom:0!important;}
.cf-sup-card .stAlert{padding:5px 8px!important;margin:4px!important;}
@media(max-width:1100px){.cf-sup-quote{min-width:220px}.cf-map-legend{display:none}.cf-sup-stat-label{white-space:normal}.cf-sla-body{gap:10px}}
@media(max-width:800px){.cf-sup-welcome{align-items:flex-start;flex-direction:column}.cf-sup-quote{width:100%;box-sizing:border-box}.cf-sup-greeting{font-size:22px}}

</style>
"""

ROLE_META = {
    "Citizen": ("🙋", "#059669"),
    "FieldTechnician": ("🔧", "#EA580C"),
    "MunicipalOfficer": ("👮", "#2563EB"),
    "Supervisor": ("🏙️", "#7C3AED"),
}

STAT_COLORS = {
    "blue":   ("#DBEAFE", "#2563EB"),
    "green":  ("#DCFCE7", "#16A34A"),
    "purple": ("#EDE9FE", "#7C3AED"),
    "red":    ("#FEE2E2", "#DC2626"),
    "orange": ("#FFEDD5", "#EA580C"),
}


def inject():
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def initials(name: str) -> str:
    parts = [p for p in re_split(name) if p]
    if not parts:
        return "U"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def re_split(name: str):
    return name.replace("-", " ").split(" ")


def brand_block():
    """Sidebar logo + tagline, matching the CivicFlow brand mark.
    Renders explicitly into the sidebar (mirrors the old st.sidebar.title call),
    so it can be invoked from app.py without a `with st.sidebar:` wrapper."""
    st.sidebar.markdown(
        """
        <div class="cf-brand">
            <div class="cf-brand-icon">🏛️</div>
            <div>
                <div class="cf-brand-title">CivicFlow</div>
                <div class="cf-brand-sub">Cleaner Cities<br>Happier Communities</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def topbar(icon: str, title: str, subtitle: str, role_label: str, user_name: str,
           location: str = "Dayalpur, Patna", notif_count: int = 0):
    """Renders the professional header bar used at the top of staff dashboards."""
    badge = f'<span class="cf-badge">{notif_count}</span>' if notif_count else ""
    st.markdown(
        f"""
        <div class="cf-topbar">
            <div class="cf-topbar-left">
                <div class="cf-topbar-logo">{icon}</div>
                <div>
                    <h1>{title}</h1>
                    <div class="cf-sub">{subtitle}</div>
                </div>
            </div>
            <div class="cf-topbar-right">
                <div class="cf-loc">📍 {location}</div>
                <div class="cf-bell">🔔{badge}</div>
                <div class="cf-avatar">{initials(user_name)}</div>
                <div class="cf-user">
                    <b>{user_name}</b>
                    <span>{role_label}</span>
                </div>
                <div class="cf-chevron">⌄</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def citizen_topbar(user_name: str, role_label: str, location: str = "Dayalpur, Patna",
                    notif_count: int = 0):
    """Search-bar style top bar used on the citizen dashboard."""
    badge = f'<span class="cf-badge">{notif_count}</span>' if notif_count else ""
    st.markdown(
        f"""
        <div class="cf-topbar cf-topbar-light">
            <div class="cf-search">
                <span>🔍</span>
                <span class="cf-search-placeholder">Search issues, wards, or ticket ID...</span>
            </div>
            <div class="cf-topbar-right">
                <div class="cf-loc-light">📍 {location}</div>
                <div class="cf-bell-light">🔔{badge}</div>
                <div class="cf-avatar">{initials(user_name)}</div>
                <div class="cf-user-light">
                    <b>{user_name}</b>
                    <span>{role_label}</span>
                </div>
                <div class="cf-chevron">⌄</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def supervisor_topbar(user_name: str, role_label: str, location: str = "Dayalpur, Patna", notif_count: int = 8):
    badge = f'<span class="cf-badge">{notif_count}</span>' if notif_count else ""
    st.markdown(
        f"""
        <div class="cf-topbar cf-topbar-light cf-supervisor-topbar">
            <div class="cf-search">
                <span>🔍</span>
                <span class="cf-search-placeholder">Search tickets, wards, departments...</span>
            </div>
            <div class="cf-topbar-right">
                <div class="cf-loc-light">📍 {location}</div>
                <div class="cf-bell-light">🔔{badge}</div>
                <div class="cf-avatar" style="background:linear-gradient(135deg,#6952D9,#805EEA);">{initials(user_name)}</div>
                <div class="cf-user-light"><b>{user_name}</b><span>{role_label}</span></div>
                <div class="cf-chevron">⌄</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def urgency_pill(urgency: int) -> str:
    cls = {5: "cf-pill-red", 4: "cf-pill-orange", 3: "cf-pill-yellow"}.get(urgency, "cf-pill-green")
    label = {5: "🔴 Critical", 4: "🟠 High", 3: "🟡 Medium"}.get(urgency, "🟢 Low")
    return f'<span class="cf-pill {cls}">{label}</span>'


def stat_card(icon: str, value, label: str, color: str = "blue", extra: str = "") -> str:
    """A small dashboard stat tile: icon square + big number + label (+ optional trend line)."""
    bg, fg = STAT_COLORS.get(color, STAT_COLORS["blue"])
    extra_html = f'<div class="cf-stat-extra">{extra}</div>' if extra else ""
    return (
        f'<div class="cf-stat-card">'
        f'<div class="cf-stat-icon" style="background:{bg};color:{fg};">{icon}</div>'
        f'<div>'
        f'<div class="cf-stat-value">{value}</div>'
        f'<div class="cf-stat-label">{label}</div>'
        f'{extra_html}'
        f'</div></div>'
    )