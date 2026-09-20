"""Role-specific dashboards: Citizen, Officer / Field Technician, Supervisor."""
from datetime import timedelta

import pandas as pd
import streamlit as st

import ai_insights
import core
import evidence
import geo_intel as geo
import hotspots
import lifecycle as lc
import sla_escalation as sla
import theme

ss = st.session_state
ROLE_LABELS = {"Citizen": "Citizen", "FieldTechnician": "Field Technician",
               "MunicipalOfficer": "Municipal Officer", "Supervisor": "Supervisor"}

SAMPLES = {
    "Custom": "",
    "🚨 High voltage cable snapped (Ward 12)": "DANGER: High voltage electric cable snapped hanging over school street in Dayalpur Daulatpur!",
    "⚠️ Water pipe burst (Main Market)": "Bohot bada paani ka pipe phat gaya hai main market chowk par! Poori sadak doob gayi hai.",
    "🧹 Sanitation overflow (Ward 14)": "Hamare area Ward 14 me picchle 4 din se kachra gaadi nahi aayi hai. Naali ke paas bohot kachra jama ho gaya hai.",
    "💡 Street light hazard (Sector 4)": "Street light pole number 14 cover is loose near Sector 4. Please send maintenance crew.",
}

LANG_PILL = {"Hindi": "cf-pill-orange", "Hinglish": "cf-pill-blue", "English": "cf-pill-grey"}

STATE_PILL = {
    "NEW": "cf-pill-grey", "AI TRIAGED": "cf-pill-blue", "ASSIGNED": "cf-pill-blue",
    "IN PROGRESS": "cf-pill-orange", "AWAITING APPROVAL": "cf-pill-yellow",
    "RESOLVED": "cf-pill-green", "CITIZEN VERIFIED": "cf-pill-green", "CLOSED": "cf-pill-grey",
}

CITIZEN_PAGES = ["Home", "Report an Issue", "My Complaints", "Track Status",
                 "Map & Hotspots", "Give Feedback", "Community", "Help & Support"]
CITIZEN_ICONS = {"Home": "🏠", "Report an Issue": "➕", "My Complaints": "📄",
                 "Track Status": "🧭", "Map & Hotspots": "🗺️", "Give Feedback": "💬",
                 "Community": "👥", "Help & Support": "❓"}

COMMON_ISSUES = [
    ("🚨", "Street Light Not Working", "💡 Street light hazard (Sector 4)"),
    ("💧", "Water Supply Issue", "⚠️ Water pipe burst (Main Market)"),
    ("🗑️", "Garbage Not Collected", "🧹 Sanitation overflow (Ward 14)"),
    ("🕳️", "Pothole / Road Damage", None),
    ("🌊", "Drainage Problem", None),
    ("⋯", "Other Issue", None),
]


def select_ticket(tid):            # button callback
    ss["selected_ticket"] = tid


def _actor_name(role):
    return ss.get("actor_name", ROLE_LABELS.get(role, role))


def _status_pill(t: dict) -> str:
    cls = STATE_PILL.get(t["state"], "cf-pill-grey")
    return f'<span class="cf-pill {cls}">{lc.STATE_LABELS[t["state"]]}</span>'


# =====================================================================
# CITIZEN
# =====================================================================
def _status_line(t):
    cur = lc.STATE_LABELS[t["state"]]
    if not lc.is_active(t):
        return f"{cur} ✓"
    trans = [h["state"] for h in t["history"] if h["kind"] == "transition"]
    return f"{lc.STATE_LABELS[trans[-2]]} → {cur}" if len(trans) >= 2 else cur


def _citizen_nav():
    ss.setdefault("citizen_page", "Home")
    st.sidebar.markdown('<div class="cf-side-menu-label">MENU</div>', unsafe_allow_html=True)
    for p in CITIZEN_PAGES:
        active = ss["citizen_page"] == p
        if st.sidebar.button(f"{CITIZEN_ICONS[p]}  {p}", key=f"cfnav_{p}", use_container_width=True,
                             type="primary" if active else "secondary"):
            ss["citizen_page"] = p
            st.rerun()
    st.sidebar.markdown(
        """<div class="cf-citizen-side-footer">
            <div class="cf-city-art"><div class="b1"></div><div class="b2"></div><div class="b3"></div><div class="b4"></div><div class="sky"></div></div>
            <div style="font-size:17px;color:#198B4C;">🌿</div>
            <b style="font-size:15px;">Your Voice</b><br>
            <span>A Better Tomorrow</span>
        </div>""", unsafe_allow_html=True)


def _citizen_stats(mine: list, NOW) -> dict:
    resolved = [t for t in mine if t["state"] in ("RESOLVED", "CITIZEN VERIFIED", "CLOSED")]
    in_progress = [t for t in mine if t["state"] == "IN PROGRESS"]
    pending_review = [t for t in mine if t["state"] == "AWAITING APPROVAL"
                      or (t.get("resolution") and t["resolution"].get("flagged"))]
    week = timedelta(days=7)
    recent = sum(1 for t in resolved if t["resolved_at"] and NOW - t["resolved_at"] <= week)
    prior = sum(1 for t in resolved if t["resolved_at"] and week < NOW - t["resolved_at"] <= 2 * week)
    delta = (recent - prior) / prior if prior else None
    avg_days = (sum((NOW - t["created_at"]).total_seconds() for t in in_progress) / len(in_progress) / 86400
               if in_progress else None)
    return {"total": len(mine), "resolved": len(resolved), "in_progress": len(in_progress),
            "pending_review": len(pending_review), "resolved_delta": delta, "avg_days": avg_days}


def _intake():
    # Compact citizen-facing intake matching the reference dashboard.
    top1, top2 = st.columns([3.4, 1])
    with top2:
        st.selectbox("🌐 Language", ["Auto-detect", "English", "Hindi", "Hinglish"], key="citizen_lang_pref")

    with st.expander("Try a sample complaint", expanded=False):
        keys = list(SAMPLES.keys())
        default_idx = keys.index(ss["citizen_sample_choice"]) if ss.get("citizen_sample_choice") in SAMPLES else 0
        choice = st.selectbox("Sample", keys, index=default_idx, key="citizen_sample_select")
        if st.button("Use this sample", key="use_citizen_sample"):
            ss["citizen_sample_choice"] = choice
            st.rerun()

    tab_text, tab_voice, tab_photo, tab_doc = st.tabs(["📄  Text", "🎙  Voice", "🖼  Photo", "📎  Document"])
    raw = ""
    with tab_text:
        raw = st.text_area(
            "Describe what happened...", value="", height=118,
            key="citizen_issue_text",
            placeholder="e.g. broken streetlight, water leakage, garbage pile"
        )
        if ss.get("citizen_sample_choice") in SAMPLES and ss.get("citizen_sample_choice") != "Custom" and not raw.strip():
            raw = SAMPLES[ss["citizen_sample_choice"]]
    with tab_voice:
        if st.audio_input("Record citizen voice grievance:"):
            st.info("🎙️ Voice note recorded (demo transcription).")
            raw = "Bohot bada paani ka pipe phat gaya hai main market chowk par! Immediate action required."
    with tab_photo:
        img = st.file_uploader("Upload visual evidence:", type=["jpg", "jpeg", "png"], key="cit_photo")
        cap = st.text_input("Optional notes with photo:", value="Broken cable hanging near school in Dayalpur.")
        if img is not None:
            st.image(img, caption="Uploaded complaint evidence", use_container_width=True)
            raw = f"[EVIDENCE ATTACHED: Image verified] {cap}"
    with tab_doc:
        docf = st.file_uploader("Upload supporting document:", type=["pdf", "doc", "docx"], key="cit_doc")
        doc_notes = st.text_input("Notes about the document:", value="", placeholder="e.g. Prior complaint acknowledgement copy")
        if docf is not None:
            st.success(f"📎 {docf.name} attached")
            raw = f"[DOCUMENT ATTACHED: {docf.name}] {doc_notes}"

    loc_col1, loc_col2 = st.columns([3, 1])
    ss.setdefault("citizen_loc_input", "")
    location_val = loc_col1.text_input("Location (optional)", key="citizen_loc_input", placeholder="e.g. Dayalpur, Ward 12")
    if loc_col2.button("📍 Use my location", use_container_width=True):
        ss["citizen_loc_input"] = "Dayalpur, Ward 12"
        st.rerun()
    category_choice = st.selectbox("Category (auto-detect)", ["Auto-detect", "Electrical", "Water", "Roads", "Sanitation", "Other"])

    if st.button("➤  Submit Complaint", type="primary", use_container_width=True):
        if not raw.strip():
            st.warning("Please describe the issue first.")
            return
        prefix = []
        if location_val.strip():
            prefix.append(f"Location: {location_val.strip()}.")
        if category_choice != "Auto-detect":
            prefix.append(f"(Category: {category_choice})")
        full_raw = (" ".join(prefix) + " " + raw) if prefix else raw
        ok = False
        with st.spinner("AI is triaging your complaint..."):
            try:
                core.ingest_complaint(full_raw)
                ok = True
            except Exception as e:
                st.error(f"Error running agent pipeline: {e}")
        if ok:
            ss["citizen_sample_choice"] = "Custom"
            st.rerun()


def _language_block(tk):
    """Feature 13 — multilingual support, made visible in the UI."""
    lang = tk.get("language", "English")
    pill_cls = LANG_PILL.get(lang, "cf-pill-grey")
    html = f'<p style="margin:4px 0;color:#1F2937;"><b>🌐 Language:</b> <span class="cf-pill {pill_cls}">{lang}</span></p>'
    if tk.get("translation"):
        html += (f'<p style="margin:4px 0;color:#1F2937;"><b>🔤 Translation:</b> '
                 f'<i>"{tk["translation"]}"</i></p>')
    return html


def _routing_card():
    st.subheader("AI routing result")
    res = ss.get("active_result")
    if not res or res["master_id"] not in core.tickets():
        st.info("Submit a complaint to see how the AI routes it.")
        return
    tk = core.tickets()[res["master_id"]]
    st.markdown(
        '<div style="border:2px solid #FF9900;padding:16px;border-radius:10px;background-color:#FFF8F0;color:#111;">'
        f'<h3 style="margin:0 0 8px 0;color:#D97706;">🎫 {tk["ticket_id"]}</h3>'
        + _language_block(tk) +
        f'<p style="margin:4px 0;color:#1F2937;"><b>🏢 Department:</b> {tk["category"]}</p>'
        f'<p style="margin:4px 0;color:#1F2937;"><b>📍 Ward:</b> {tk["ward"]}</p>'
        f'<p style="margin:4px 0;color:#1F2937;"><b>👷 Team:</b> {tk["team"]}</p>'
        f'<p style="margin:4px 0;color:#DC2626;"><b>⚡ Priority:</b> {tk["priority_label"]}</p>'
        f'<p style="margin:4px 0;color:#065F46;"><b>🛠️ Action:</b> {tk["recommended_action"]}</p>'
        f'<p style="margin:6px 0 0 0;color:#6B7280;font-size:13px;"><b>🔥 Public impact:</b> {tk["reports_count"]} citizen report(s)</p>'
        "</div>", unsafe_allow_html=True)


def _citizen_confirm(t):
    tid = t["ticket_id"]
    st.success("✅ Your complaint has been resolved.")
    res = t.get("resolution")
    if res and res.get("photo"):
        st.image(res["photo"], caption="Photo of completed repair", width=320)
    st.markdown("**Was this issue resolved?**")
    reason = st.text_input("If not, what is still wrong? (required for 👎)", key=f"reason_{tid}_{t['reopen_count']}")
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("👍 Yes", key=f"yes_{tid}"):
        core.citizen_respond(t, True)
        st.rerun()
    if b2.button("👎 No", key=f"no_{tid}"):
        core.citizen_respond(t, False, reason)
        st.rerun()


def _citizen_card(t):
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.1, 2.6, 2])
        c1.markdown(f"**{t['ticket_id']}**  \n{core.BADGES[t['urgency']]}")
        c2.markdown(f"**{t['title']}**  \n{t['category']} · {t['ward']}")
        c3.markdown(f"**{_status_line(t)}**")
        st.progress((lc.STATES.index(t["state"]) + 1) / len(lc.STATES))
        if t["state"] == "RESOLVED":
            _citizen_confirm(t)
        elif t["reopen_count"] and lc.is_active(t):
            st.warning("🔁 Re-opened after your feedback and escalated to a Supervisor.")
        elif t["state"] in ("CITIZEN VERIFIED", "CLOSED"):
            st.caption("You confirmed this fix. Thank you! ✓")
        with st.expander("Track progress"):
            st.markdown(lc.render_tracker_html(t), unsafe_allow_html=True)


def _mine():
    return [t for t in core.tickets().values() if "me" in t["reporters"]]


def _mini_map():
    tickets = core.tickets()
    df = geo.tickets_dataframe(tickets)
    if df.empty:
        st.caption("No active issues on the map.")
        return
    clusters = geo.ward_clusters(df)
    deck = geo.build_deck(df, clusters, show_heat=False, show_points=True, show_clusters=True)
    st.pydeck_chart(deck, use_container_width=True)
    st.caption("🔴 Electrical  🟠 Water  🟡 Roads  🔵 Sanitation  ·  circle = active complaints in ward")


def _common_issues_card():
    with st.container(border=True):
        st.markdown("##### 💡 Common Issues")
        for icon, label, sample_key in COMMON_ISSUES:
            if st.button(f"{icon}  {label}", key=f"ci_{label}", use_container_width=True):
                if sample_key:
                    ss["citizen_sample_choice"] = sample_key
                ss["citizen_page"] = "Report an Issue"
                st.rerun()


def _urgent_help_card():
    st.markdown(
        """
        <div class="cf-help-card">
            <b>📞 Need Urgent Help?</b>
            <p>Call Municipal Helpline<br><b>1800-XXX-XXXX</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _civic_awareness_card():
    st.markdown(
        """
        <div class="cf-eco-card">
            <b>🌱 Civic Awareness</b>
            <p>Keep your surroundings clean. Report issues. Build a better
            Dayalpur together!</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _my_complaints_table(mine: list, limit=None):
    rows = sorted(mine, key=lambda t: -t["latest_report"].timestamp())
    if limit:
        rows = rows[:limit]
    widths = [1.0, 2.6, 1.7, 1.0, 1.2, 1.2, 1.4, 0.8]
    header = st.columns(widths)
    for col, label in zip(header, ["Ticket ID", "Issue", "Department", "Ward", "Status",
                                   "Priority", "Last Updated", "Actions"]):
        col.markdown(f"**{label}**")
    st.markdown('<hr style="margin:4px 0 8px 0;border-color:#E5E7EB;">', unsafe_allow_html=True)
    for t in rows:
        c = st.columns(widths)
        c[0].markdown(f"`{t['ticket_id']}`")
        c[1].markdown(t["title"])
        c[2].markdown(geo.dept_style(t["category"])[0])
        c[3].markdown(t["ward"])
        c[4].markdown(_status_pill(t), unsafe_allow_html=True)
        c[5].markdown(theme.urgency_pill(t["urgency"]), unsafe_allow_html=True)
        c[6].markdown(t["latest_report"].strftime("%d %b, %H:%M"))
        if c[7].button("View", key=f"cview_{t['ticket_id']}"):
            ss["citizen_page"] = "Track Status"
            ss["citizen_detail_ticket"] = t["ticket_id"]
            st.rerun()


def _citizen_home(NOW):
    mine = _mine()
    stats = _citizen_stats(mine, NOW)

    st.markdown(
        """
        <div class="cf-welcome-row">
            <div>
                <div class="cf-welcome-title">👋 Welcome to CivicFlow!</div>
                <div class="cf-welcome-sub">Report civic issues in seconds. Together we can build
                cleaner, safer and smarter communities.</div>
            </div>
            <div class="cf-welcome-quote">🌱 "A cleaner city<br>starts with you."</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(theme.stat_card("📋", stats["total"], "Your Complaints", "blue"), unsafe_allow_html=True)
    if stats["resolved_delta"] is not None:
        extra = f'↑ {stats["resolved_delta"]:+.0%} vs last week' if stats["resolved_delta"] >= 0 \
            else f'↓ {stats["resolved_delta"]:.0%} vs last week'
    else:
        extra = ""
    c2.markdown(theme.stat_card("✅", stats["resolved"], "Resolved", "green", extra), unsafe_allow_html=True)
    sub = f'avg {stats["avg_days"]:.1f} days' if stats["avg_days"] else ""
    c3.markdown(theme.stat_card("🕑", stats["in_progress"], "In Progress", "purple", sub), unsafe_allow_html=True)
    c4.markdown(theme.stat_card("⚠️", stats["pending_review"], "Pending Review", "red"), unsafe_allow_html=True)
    with c5:
        st.markdown(
            '<div class="cf-thanks-card">🌱 <b>Thank you!</b><span>You are making a difference.</span></div>',
            unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    left, mid, right = st.columns([2.3, 2.0, 1.4])
    with left:
        with st.container(border=True):
            st.markdown("#### 📣 Report a Civic Issue")
            _intake()
    with mid:
        with st.container(border=True):
            st.markdown("#### 🗺️ Issue Map")
            _mini_map()
            if st.button("View Full Map →", use_container_width=True):
                ss["citizen_page"] = "Map & Hotspots"
                st.rerun()
    with right:
        _common_issues_card()
        _urgent_help_card()
        _civic_awareness_card()

    st.markdown("---")
    tc1, tc2 = st.columns([5, 1])
    tc1.subheader("📄 My Complaints")
    if tc2.button("View All →", use_container_width=True):
        ss["citizen_page"] = "My Complaints"
        st.rerun()
    if not mine:
        st.info("You have not reported any complaints yet.")
    else:
        _my_complaints_table(mine, limit=4)


def _citizen_report_page():
    st.subheader("📝 Report an Issue")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            _intake()
    with right:
        _routing_card()


def _citizen_my_complaints():
    st.subheader("📄 My Complaints")
    mine = _mine()
    if not mine:
        st.info("You have not reported any complaints yet.")
        return
    _my_complaints_table(mine)


def _citizen_track_status(NOW):
    st.subheader("🧭 Track Status")
    mine = _mine()
    if not mine:
        st.info("You have not reported any complaints yet.")
        return
    detail_id = ss.get("citizen_detail_ticket")
    my_ids = {t["ticket_id"] for t in mine}
    if detail_id and detail_id in my_ids:
        t = core.tickets()[detail_id]
        if st.button("← Back to all complaints"):
            ss["citizen_detail_ticket"] = None
            st.rerun()
        _case_summary_card(t, NOW)
        _citizen_card(t)
    else:
        for t in sorted(mine, key=lambda t: (not lc.is_active(t) and t["state"] != "RESOLVED",
                                             -t["created_at"].timestamp())):
            _citizen_card(t)


def _citizen_map_page(NOW):
    st.subheader("🗺️ Map & Hotspots")
    tickets = core.tickets()
    hs = hotspots.detect_hotspots(tickets, NOW)
    geo.render_geo_section(tickets, lambda t: sla.sla_status(t, NOW),
                           [h["ward"] for h in hs if h["status"] == "HOTSPOT"])
    st.markdown("---")
    render_hotspots(hs)


def _citizen_feedback():
    st.subheader("💬 Give Feedback")
    st.caption("Tell us how CivicFlow is working for you — this helps the city improve the service.")
    ss.setdefault("feedback_log", [])
    with st.container(border=True):
        rating = st.select_slider("Overall experience", options=["😞", "😐", "🙂", "😃", "🤩"], value="🙂")
        text = st.text_area("Your feedback", placeholder="What's working well? What could be better?")
        if st.button("Submit Feedback", type="primary"):
            if text.strip():
                ss["feedback_log"].append({"rating": rating, "text": text.strip()})
                st.success("🙏 Thanks for your feedback — it's been recorded.")
            else:
                st.warning("Please write a short note before submitting.")
    if ss["feedback_log"]:
        st.markdown("##### Your recent feedback")
        for f in reversed(ss["feedback_log"][-5:]):
            st.markdown(f"{f['rating']} — {f['text']}")


def _citizen_community():
    st.subheader("👥 Community")
    st.caption("Civic tips and what's happening across the city right now.")
    tickets = core.tickets()
    hs = hotspots.detect_hotspots(tickets, core.now())
    if hs:
        st.markdown("##### 🔥 Active hotspots near you")
        for h in hs[:3]:
            st.info(f"**{h['ward']}** — {h['headline']}")
    else:
        st.success("No active hotspots right now — things are looking calm across the city. 🎉")
    st.markdown("##### 🌱 Civic tips")
    for tip in [
        "Segregate wet and dry waste before it's collected — it speeds up processing.",
        "Report streetlight or pole hazards immediately — these are treated as safety-critical.",
        "Add a photo with your complaint; it helps officers verify the issue faster.",
        "Upvote/report duplicates instead of filing a new ticket — it raises priority automatically.",
    ]:
        st.markdown(f"- {tip}")


def _citizen_help():
    st.subheader("❓ Help & Support")
    _urgent_help_card()
    st.markdown("##### Frequently asked questions")
    with st.expander("How does CivicFlow decide who handles my complaint?"):
        st.write("An AI triage step reads your complaint (in English, Hindi or Hinglish), "
                "classifies the department, ward and urgency, and routes it to the right crew automatically.")
    with st.expander("How long will it take to resolve my issue?"):
        st.write("Every ticket has an SLA target based on urgency (30 minutes for critical safety "
                "issues, up to 3 days for routine ones). You can track progress under **Track Status**.")
    with st.expander("What if I'm not satisfied with the fix?"):
        st.write("On the resolved ticket, choose 👎 and tell us what's still wrong — this reopens "
                "the ticket and escalates it straight to a Supervisor.")
    with st.expander("Is my language supported?"):
        st.write("Yes — English, Hindi and Hinglish (romanized Hindi) are all detected automatically, "
                "and a plain-English gloss is generated for officers.")


def render_citizen(NOW):
    # _citizen_nav()
    # stats = _citizen_stats(_mine(), NOW)
    # theme.citizen_topbar(_actor_name("Citizen"), "Citizen",
    #                      notif_count=stats["pending_review"] + stats["in_progress"])
    core.show_flash()

    page = ss.get("citizen_page", "Home")
    if page == "Home":
        _citizen_home(NOW)
    elif page == "Report an Issue":
        _citizen_report_page()
    elif page == "My Complaints":
        _citizen_my_complaints()
    elif page == "Track Status":
        _citizen_track_status(NOW)
    elif page == "Map & Hotspots":
        _citizen_map_page(NOW)
    elif page == "Give Feedback":
        _citizen_feedback()
    elif page == "Community":
        _citizen_community()
    elif page == "Help & Support":
        _citizen_help()


# =====================================================================
# SHARED: ticket command center
# =====================================================================
def _checks_list(checks):
    icon = {"pass": "✓", "warn": "⚠️", "fail": "✗"}
    for c in checks:
        st.markdown(f"{icon[c['status']]} **{c['label']}** — {c['detail']}")


def _evidence_form(t, role):
    tid = t["ticket_id"]
    st.markdown("---")
    st.markdown(f"#### 📷 Resolution evidence — {t['title']}")
    st.caption("Officers must upload a photo of the completed work. The AI checks it before the ticket can be resolved.")
    n = t["reopen_count"]
    up = st.file_uploader("Upload resolution photo", type=["jpg", "jpeg", "png"], key=f"ev_{tid}_{n}")
    notes = st.text_input("Work notes", key=f"evn_{tid}_{n}", placeholder="e.g. Bulb replaced and pole cover fixed")
    if up is None:
        return
    data = up.getvalue()
    st.image(data, width=260)
    with st.spinner("AI verifying evidence..."):
        result = evidence.verify_resolution(data, up.name, t, notes, ss["vision_cache"])
    st.markdown(f"**AI verification** ({'vision model' if result['mode'] == 'vision' else 'heuristic checks'})")
    _checks_list(result["checks"])
    needs_review = result["verdict"] == "NEEDS REVIEW"
    if needs_review:
        st.error("Evidence did not pass verification. You can still submit, but it will be flagged for supervisor review.")
    label = "⚠️ Submit anyway (flag for review)" if needs_review else "✅ Submit Resolution"
    if st.button(label, key=f"sub_{tid}_{n}", type="primary"):
        core.submit_resolution(t, role, data, up.name, notes, result, flagged=needs_review)
        st.rerun()


def _show_resolution(t):
    res = t["resolution"]
    st.markdown("---")
    st.markdown("#### 🧾 Resolution evidence on file")
    c1, c2 = st.columns([1, 2])
    if res.get("photo"):
        c1.image(res["photo"], width=240)
    with c2:
        if res["flagged"]:
            st.warning("RESOLUTION FLAGGED — evidence needs supervisor review")
        elif res["verdict"].startswith("VERIFIED"):
            (st.success if res["verdict"] == "VERIFIED" else st.info)(f"RESOLUTION {res['verdict']}")
        if res.get("notes"):
            st.markdown(f"**Notes:** {res['notes']}")
        _checks_list(res.get("checks", []))
        st.caption(f"Submitted by {res['by']} at {res['at']:%d %b %H:%M}")


def _authz_flow(t, d):
    ok = d["allowed"]
    steps = [(f"{ROLE_LABELS.get(d['principal'], d['principal'])} opens {t['ticket_id']}", None),
             (f"Attempts {core.inr(d['cost'])} emergency dispatch", None),
             ("Cedar evaluates policy", None),
             ("✓ ALLOW" if ok else "✗ DENY", "#16A34A" if ok else "#DC2626"),
             ("Dispatch triggered" if ok else "Dispatch blocked", "#16A34A" if ok else "#DC2626")]
    parts = []
    for i, (txt, col) in enumerate(steps):
        style = f"color:{col};font-weight:700;" if col else ""
        parts.append(f'<div style="{style}">{txt}</div>')
        if i < len(steps) - 1:
            parts.append('<div style="color:#9CA3AF;">↓</div>')
    return '<div style="text-align:center;line-height:1.7;">' + "".join(parts) + "</div>"


def _authz_expander(t):
    d = t["authz"][-1]
    with st.expander("🔐 Authorization Details", expanded=not d["allowed"]):
        a, b = st.columns([1, 1.3])
        a.markdown(_authz_flow(t, d), unsafe_allow_html=True)
        with b:
            st.markdown("**🔐 Authorization Decision**")
            st.markdown(f"**Principal:** `{d['principal']}`  \n**Action:** `{d['action']}`  \n"
                        f"**Resource:** `{d['resource']}`  \n**Urgency:** {d['urgency']}  \n"
                        f"**Estimated cost:** {core.inr(d['cost'])}")
            st.markdown(f"**Decision:** {'✓ ALLOW' if d['allowed'] else '✗ DENY'}  \n**Policy:** `{d['policy']}`")
            (st.success if d["allowed"] else st.error)(f"**Reason:** {d['reason']}")
            st.caption(f"Evaluated by {d['engine']} · {len(t['authz'])} decision(s) on this ticket")


def _case_summary_card(t, NOW):
    """Feature 14 — AI-generated complaint summary so officers don't have to
    read the raw citizen message."""
    summary = ai_insights.generate_case_summary(t, NOW)
    impact_html = "".join(f'<div class="cf-row">• {i}</div>' for i in summary["impact"])
    lang_html = ""
    if t.get("translation"):
        lang_html = (f'<div class="cf-row"><b>Original ({t["language"]}):</b> '
                     f'<i>"{t["evidence_list"][-1] if t["evidence_list"] else t["title"]}"</i></div>'
                     f'<div class="cf-row"><b>Translated:</b> "{t["translation"]}"</div>')
    st.markdown(
        f"""
        <div class="cf-ai-card">
            <h4>📋 AI CASE SUMMARY</h4>
            {lang_html}
            <div class="cf-row"><b>Problem:</b> {summary['problem']}</div>
            <div class="cf-row"><b>Location:</b> {summary['location']}</div>
            <div class="cf-row"><b>Duration open:</b> {summary['duration']}</div>
            <div class="cf-row"><b>Impact:</b></div>
            {impact_html}
            <div class="cf-row"><b>Priority:</b> {summary['priority']}</div>
            <div class="cf-row"><b>Recommended action:</b> {summary['recommended_action']}</div>
            <div class="cf-row" style="color:#6B7280;font-size:12px;margin-top:6px;">
                Based on {summary['reports']} citizen report(s) — generated automatically, no need to read the raw message.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_command_center(role, NOW):
    tickets = core.tickets()
    st.subheader("🎟️ Ticket Command Center")
    ids = list(tickets.keys())
    if ss.get("selected_ticket") not in ids:
        ss["selected_ticket"] = "CF-1042" if "CF-1042" in ids else ids[0]
    sel = st.selectbox("Select ticket", ids, key="selected_ticket",
                       format_func=lambda i: f"{i} · {tickets[i]['category']} · {lc.STATE_LABELS[tickets[i]['state']]}")
    t = tickets[sel]
    s = sla.sla_status(t, NOW)

    _case_summary_card(t, NOW)

    c_life, c_sla, c_act = st.columns([1.1, 1.2, 1])
    with c_life:
        st.markdown("#### 🔁 Lifecycle")
        st.markdown(lc.render_tracker_html(t), unsafe_allow_html=True)
    with c_sla:
        st.markdown("#### ⏳ SLA")
        st.markdown(f"**Urgency:** {t['urgency']}/5 · **SLA target:** {sla.fmt_duration(s['target'])}")
        st.markdown(f"**Elapsed:** {sla.fmt_duration(s['elapsed'])}")
        st.progress(min(max(s["pct"], 0.0), 1.0))
        {"ON TRACK": st.success, "MET": st.success, "AT RISK": st.warning,
         "BREACHED": st.error, "MISSED": st.error}[s["status"]](s["message"])
        st.markdown("**Escalation path**")
        st.markdown(sla.render_chain_html(t["escalation_level"], lc.is_active(t)), unsafe_allow_html=True)
    with c_act:
        st.markdown("#### 🎬 Actions")
        st.caption(f"Signed in as **{ROLE_LABELS[role]}**")
        actions = lc.available_actions(t)
        if not actions:
            st.info("Lifecycle complete — ticket closed.")
        elif all(a.roles == ("Citizen",) for a in actions):
            st.info("⏳ Waiting for the citizen to confirm the fix.")
        for a in actions:
            if a.roles == ("Citizen",):
                continue
            if a.needs_evidence:
                st.caption("📷 Upload resolution evidence below." if role in a.roles
                           else f"Requires: {', '.join(a.roles)}")
                continue
            label = "🚒 Dispatch crew" if a.cedar else a.label
            if a.cedar:
                st.caption(f"Estimated dispatch cost: {core.inr(t['dispatch_cost'])}")
            if st.button(label, key=f"act_{sel}_{a.target}", disabled=role not in a.roles,
                         use_container_width=True):
                core.dispatch_crew(t, role) if a.cedar else core.do_step(t, a, role)
                st.rerun()
            if role not in a.roles:
                st.caption(f"Requires: {', '.join(a.roles)}")

    if t["state"] == "IN PROGRESS" and role in lc.STAFF:
        _evidence_form(t, role)
    if t.get("resolution"):
        _show_resolution(t)

    report = sla.build_escalation_report(t, s)
    if report:
        with st.container(border=True):
            (st.error if s["status"] == "BREACHED" or t["reopen_count"] else st.warning)("⚠️ ESCALATION RECOMMENDED")
            st.markdown(f"**Complaint:** {report['complaint']}")
            st.markdown("**Reasons:**\n" + "\n".join(f"- {r}" for r in report["reasons"]))
            st.markdown(f"**Recommended action:** {report['action']}")

    if t["authz"]:
        _authz_expander(t)
    with st.expander("🕓 Ticket history"):
        for h in reversed(t["history"]):
            tag = "" if h["kind"] == "transition" else "📝 "
            st.caption(f"{h['at']:%d %b %H:%M:%S} · {tag}{lc.STATE_LABELS[h['state']]} · {h['actor']}"
                       + (f" — {h['note']}" if h["note"] else ""))


# =====================================================================
# OFFICER / FIELD TECHNICIAN
# =====================================================================
def _queue_rows(items, statuses, prefix):
    for t in items:
        s = statuses[t["ticket_id"]]
        c = st.columns([0.9, 1.0, 3, 1.5, 2.3, 0.7])
        c[0].markdown(f"**{t['ticket_id']}**")
        c[1].markdown(core.BADGES[t["urgency"]])
        c[2].markdown(f"{t['title']}  \n<span style='color:#9CA3AF;font-size:12px;'>{t['ward']} · {t['category']}</span>",
                      unsafe_allow_html=True)
        c[3].markdown(lc.STATE_LABELS[t["state"]])
        c[4].markdown(s["message"])
        c[5].button("Open", key=f"{prefix}_{t['ticket_id']}", on_click=select_ticket, args=(t["ticket_id"],))


def render_officer(role, NOW):
    crew = role == "FieldTechnician"
    theme.topbar("🔧" if crew else "👮", "CivicFlow", "On the ground. In action." if crew else "Approve, allocate, monitor.",
                 ROLE_LABELS[role], _actor_name(role))
    core.show_flash()
    active = [t for t in core.tickets().values() if lc.is_active(t)]
    if crew:
        active = [t for t in active if t["state"] in ("ASSIGNED", "IN PROGRESS")]
    statuses = {t["ticket_id"]: sla.sla_status(t, NOW) for t in active}
    st.subheader("Your crew queue" if crew else "Assigned to you")

    n = lambda f: sum(1 for t in active if f(t["urgency"]))
    m = st.columns(5)
    m[0].metric("🔴 Critical", n(lambda u: u == 5))
    m[1].metric("🟠 High", n(lambda u: u == 4))
    m[2].metric("🟡 Medium", n(lambda u: u == 3))
    m[3].metric("🟢 Low", n(lambda u: u <= 2))
    risky = [t for t in active if statuses[t["ticket_id"]]["status"] in ("AT RISK", "BREACHED")]
    m[4].metric("SLA at risk", len(risky))

    waiting = [t for t in active if t["state"] == "AWAITING APPROVAL"]
    if waiting and not crew:
        st.warning(f"📝 {len(waiting)} resolution(s) awaiting your approval: " + ", ".join(t["ticket_id"] for t in waiting))
    if not active:
        st.success("Nothing in your queue. 🎉")
    _queue_rows(sorted(active, key=lambda t: -statuses[t["ticket_id"]]["pct"]), statuses, "q")
    st.markdown("---")
    render_command_center(role, NOW)


# =====================================================================
# SUPERVISOR
# =====================================================================
def render_hotspots(hs, limit=3):
    st.subheader("🔥 AI Hotspot Detection")
    if not hs:
        st.success("No emerging hotspots in the last 24 hours.")
        return
    for h in hs[:limit]:
        with st.container(border=True):
            st.markdown(f"### {'🔥' if h['status'] == 'HOTSPOT' else '👀'} {h['headline']}")
            g = h["growth_total"]
            st.caption(f"{h['recent_total']} complaints in the last 24h vs {h['prior_total']} in the 24h before"
                       + (f" ({g:+.0%})" if g is not None else " (no prior activity)"))
            st.markdown("**Because — last 24 hours vs previous 24 hours:**\n" + "\n".join(f"- {b}" for b in h["because"]))
            st.info(f"**Recommended:** {h['recommendation']}")


def _analytics_section(tickets, NOW):
    """Feature 15 — expanded analytics dashboard."""
    st.subheader("📊 Analytics")
    all_t = list(tickets.values())
    active = [t for t in all_t if lc.is_active(t)]
    critical = sum(1 for t in active if t["urgency"] == 5)
    resolved = sum(1 for t in all_t if not lc.is_active(t))
    met = sum(1 for t in all_t if not lc.is_active(t) and sla.sla_status(t, NOW)["status"] == "MET")
    sla_pct = (met / resolved * 100) if resolved else 100

    m = st.columns(4)
    m[0].metric("Active", len(active))
    m[1].metric("Critical", critical)
    m[2].metric("Resolved", resolved)
    m[3].metric("SLA Met", f"{sla_pct:.0f}%")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Complaints by category**")
        by_cat = {}
        for t in all_t:
            label = geo.dept_style(t["category"])[0]
            by_cat[label] = by_cat.get(label, 0) + t["reports_count"]
        if by_cat:
            df = pd.DataFrame({"Complaints": by_cat}).sort_values("Complaints", ascending=False)
            st.bar_chart(df)
    with c2:
        st.markdown("**Avg. resolution time by department (hrs)**")
        durations = {}
        for t in all_t:
            if t["resolved_at"]:
                label = geo.dept_style(t["category"])[0]
                hrs = (t["resolved_at"] - t["created_at"]).total_seconds() / 3600
                durations.setdefault(label, []).append(hrs)
        if durations:
            avg = {k: round(sum(v) / len(v), 1) for k, v in durations.items()}
            df = pd.DataFrame({"Avg hours": avg}).sort_values("Avg hours")
            st.bar_chart(df)
        else:
            st.caption("No resolved tickets yet.")

    st.markdown("**Ward performance — % SLA met (closed tickets)**")
    ward_perf = {}
    for t in all_t:
        if not lc.is_active(t):
            ward_perf.setdefault(t["ward"], []).append(
                1 if sla.sla_status(t, NOW)["status"] == "MET" else 0)
    if ward_perf:
        rows = sorted(((w, sum(v) / len(v) * 100) for w, v in ward_perf.items()),
                      key=lambda x: -x[1])
        for w, pct in rows:
            flag = " ⚠️" if pct < 80 else ""
            st.markdown(f"**{w}** — {pct:.0f}%{flag}")
            st.progress(min(max(pct / 100, 0.0), 1.0))
    else:
        st.caption("No closed tickets yet to compute ward performance.")


def _priority_brief_section(tickets, hs, NOW):
    """Feature 16 — the 'what should I fix first' killer feature."""
    st.subheader("🤖 AI Priority Brief")
    st.caption("The AI analyzes current complaints across every ward and tells you what to fix first.")
    if st.button("🤖 Generate Priority Brief", type="primary"):
        ss["priority_brief"] = ai_insights.generate_priority_brief(tickets, hs, NOW)
    brief = ss.get("priority_brief")
    if not brief:
        st.info("Click the button to generate today's city priority brief.")
        return
    st.markdown("#### CITY PRIORITY BRIEF")
    for b in brief:
        st.markdown(
            f"""
            <div class="cf-brief-card">
                <div style="font-weight:800;font-size:15px;margin-bottom:6px;">{b['tier']}<br>
                    <span style="font-weight:700;">Ward {b['ward'].replace('Ward','').strip()} — {b['department']}</span>
                </div>
                <div style="font-size:13.5px;color:#374151;">
                    {b['complaints']} complaint(s) · {b['critical']} critical<br>
                    {b['trend_note']}
                </div>
                <div style="margin-top:8px;font-size:13.5px;color:#1F2937;">
                    <b>Recommendation:</b> {b['recommendation']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_registry(NOW):
    st.subheader("📊 Master Ticket Registry")
    rows = []
    for t in core.tickets().values():
        s = sla.sla_status(t, NOW)
        rows.append({"Ticket ID": t["ticket_id"], "Department": t["category"], "Ward": t["ward"],
                     "Priority": t["priority_label"], "State": lc.STATE_LABELS[t["state"]], "SLA": s["status"],
                     "Language": t.get("language", "English"),
                     "Escalated To": sla.CHAIN_LABELS[sla.CHAIN[t["escalation_level"]]],
                     "Reports": t["reports_count"], "Re-opened": t["reopen_count"]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if ss["audit_log"]:
        st.subheader("📜 Authorization, Lifecycle & Escalation Audit Log")
        st.dataframe(pd.DataFrame(ss["audit_log"][::-1]), use_container_width=True, hide_index=True)


def _supervisor_icon_stat(icon, value, label, color="blue", trend="", trend_color="#16A34A"):
    bg, fg = theme.STAT_COLORS.get(color, theme.STAT_COLORS["blue"])
    trend_html = f'<div class="cf-sup-trend" style="color:{trend_color};">{trend}</div>' if trend else ""
    return f"""
    <div class="cf-sup-stat">
        <div class="cf-sup-stat-icon" style="background:{bg};color:{fg};">{icon}</div>
        <div class="cf-sup-stat-main">
            <div class="cf-sup-stat-value">{value}</div>
            <div class="cf-sup-stat-label">{label}</div>
            {trend_html}
        </div>
    </div>
    """


def _supervisor_critical_panel(active, statuses):
    critical = sorted(
        [t for t in active if t["urgency"] >= 4 or statuses[t["ticket_id"]]["status"] in ("AT RISK", "BREACHED")],
        key=lambda t: (-int(statuses[t["ticket_id"]]["status"] == "BREACHED"), -t["urgency"], -statuses[t["ticket_id"]]["pct"]),
    )[:6]
    st.markdown('<div class="cf-sup-card cf-sup-critical-card">', unsafe_allow_html=True)
    st.markdown('<div class="cf-sup-card-head"><div><span class="cf-section-icon red">⚠</span><b>Critical &amp; Escalated Tickets</b></div><span class="cf-view-all">View All →</span></div>', unsafe_allow_html=True)
    if not critical:
        st.success("No critical or escalated tickets right now.")
    for t in critical:
        s = statuses[t["ticket_id"]]
        status = s["status"]
        urgency = "Critical" if t["urgency"] == 5 else "High"
        status_text = "SLA BREACHED" if status == "BREACHED" else (f"SLA risk: {max(1, int((1-s['pct'])*60))} min" if status == "AT RISK" else "Escalated")
        action = "Review" if status == "BREACHED" else ("Take Action" if status == "AT RISK" else "View")
        dot = "red" if t["urgency"] == 5 else "orange"
        st.markdown(f"""
        <div class="cf-critical-row">
            <div class="cf-critical-main">
                <div><b>{t['ticket_id']}</b> <span class="cf-dot {dot}"></span> <span>{urgency}</span>
                <span class="cf-critical-status">{status_text}</span></div>
                <div class="cf-critical-title">{t['title']}</div>
                <div class="cf-critical-meta">{t['ward']} · {t['category']}</div>
            </div>
            <button class="cf-fake-action">{action}</button>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _supervisor_department_card(tickets):
    counts = {}
    for t in tickets.values():
        label = geo.dept_style(t["category"])[0]
        counts[label] = counts.get(label, 0) + t["reports_count"]
    items = sorted(counts.items(), key=lambda x: -x[1])
    max_v = max((v for _, v in items), default=1)
    rows = []
    classes = ["pink", "blue", "yellow", "green", "purple"]
    for i, (name, count) in enumerate(items[:5]):
        width = max(8, int(count / max_v * 100))
        rows.append(f'<div class="cf-bar-row"><span>{name}</span><div class="cf-bar"><i class="{classes[i % len(classes)]}" style="width:{width}%"></i></div><b>{count}</b></div>')
    st.markdown(
        '<div class="cf-sup-card cf-dept-card"><div class="cf-sup-card-head"><div><span class="cf-section-icon purple">▤</span><b>Department-wise Tickets</b></div><span class="cf-view-all">View All →</span></div>' + ''.join(rows) + '</div>',
        unsafe_allow_html=True,
    )


def _supervisor_sla_card(tickets, NOW):
    all_t = list(tickets.values())
    resolved = [t for t in all_t if not lc.is_active(t)]
    met = sum(1 for t in resolved if sla.sla_status(t, NOW)["status"] in ("MET", "ON TRACK"))
    on_time = round((met / len(resolved)) * 100) if resolved else 86
    risk = sum(1 for t in all_t if sla.sla_status(t, NOW)["status"] == "AT RISK")
    breached = sum(1 for t in all_t if sla.sla_status(t, NOW)["status"] == "BREACHED")
    risk_pct = round(risk / max(1, len(all_t)) * 100)
    breach_pct = round(breached / max(1, len(all_t)) * 100)
    st.markdown(f"""
    <div class="cf-sup-card cf-sla-card">
        <div class="cf-sup-card-head"><div><span class="cf-section-icon green">✓</span><b>SLA Compliance</b></div></div>
        <div class="cf-sla-body">
            <div class="cf-donut" style="--pct:{on_time * 3.6}deg"><div><b>{on_time}%</b><span>On Time</span></div></div>
            <div class="cf-sla-legend"><div><i class="green"></i>On Time <b>{on_time}%</b></div><div><i class="orange"></i>At Risk <b>{risk_pct}%</b></div><div><i class="red"></i>Breached <b>{breach_pct}%</b></div></div>
        </div>
    </div>""", unsafe_allow_html=True)


def _supervisor_ai_brief_card(tickets, hs, NOW):
    st.markdown('<div class="cf-sup-card cf-ai-brief"><div class="cf-sup-card-head"><div><span class="cf-section-icon purple">✦</span><b>AI Priority Brief</b></div></div>', unsafe_allow_html=True)
    try:
        brief = ai_insights.generate_priority_brief(tickets, hs, NOW)
    except Exception:
        brief = []
    if brief:
        for i, b in enumerate(brief[:4], 1):
            st.markdown(f'<div class="cf-ai-line"><span>{i}</span><p>{b["recommendation"]}</p></div>', unsafe_allow_html=True)
    else:
        top = hs[0] if hs else None
        fallback = [
            f'{top["ward"]} shows the strongest recent complaint growth.' if top else 'Review current high-priority complaints across wards.',
            'Prioritize tickets approaching or breaching their SLA.',
            'Review repeated complaints before assigning additional crews.',
            'Use the command center below for detailed ticket actions.',
        ]
        for i, text in enumerate(fallback, 1):
            st.markdown(f'<div class="cf-ai-line"><span>{i}</span><p>{text}</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _supervisor_escalation_table(active, statuses):
    rows = []
    for t in sorted(active, key=lambda x: -statuses[x["ticket_id"]]["pct"])[:8]:
        s = statuses[t["ticket_id"]]
        if t["escalation_level"] >= 2 or t["reopen_count"] or s["status"] in ("AT RISK", "BREACHED"):
            rows.append({
                "Ticket ID": t["ticket_id"], "Issue": t["title"][:28],
                "Current Role": "Field Technician", "Escalated To": "Supervisor",
                "Reason": "SLA breach" if s["status"] == "BREACHED" else ("SLA risk" if s["status"] == "AT RISK" else "Escalation"),
                "Time": s["message"].split(" — ")[0],
            })
    st.markdown('<div class="cf-sup-card cf-table-card"><div class="cf-sup-card-head"><div><span class="cf-section-icon orange">↥</span><b>Escalation Queue</b></div><span class="cf-view-all">View All →</span></div>', unsafe_allow_html=True)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=150)
    else:
        st.caption("No active escalations.")
    st.markdown('</div>', unsafe_allow_html=True)


def _supervisor_recent_activity(tickets):
    events = []
    for t in tickets.values():
        for h in t.get("history", [])[-2:]:
            events.append((h["at"], h))
    events.sort(key=lambda x: x[0], reverse=True)
    st.markdown('<div class="cf-sup-card cf-activity-card"><div class="cf-sup-card-head"><div><span class="cf-section-icon purple">◷</span><b>Recent Activity</b></div><span class="cf-view-all">View All →</span></div>', unsafe_allow_html=True)
    for at, h in events[:5]:
        st.markdown(f'<div class="cf-activity-row"><span class="cf-activity-time">{at:%H:%M}</span><span class="cf-activity-dot"></span><span>{lc.STATE_LABELS.get(h["state"], h["state"])} · {h["actor"]}</span></div>', unsafe_allow_html=True)
    if not events:
        st.caption("No recent activity.")
    st.markdown('</div>', unsafe_allow_html=True)


def _supervisor_quick_actions():
    st.markdown('''<div class="cf-sup-card cf-quick-card"><div class="cf-sup-card-head"><div><span class="cf-section-icon navy">⚙</span><b>Quick Actions</b></div></div><div class="cf-quick-grid">
        <div class="cf-quick-btn green">✓<span>Approve Requests</span></div>
        <div class="cf-quick-btn purple">↗<span>Reassign Ticket</span></div>
        <div class="cf-quick-btn blue">➤<span>Send Notification</span></div>
        <div class="cf-quick-btn orange">▤<span>Generate Report</span></div>
    </div></div>''', unsafe_allow_html=True)


def render_supervisor(NOW):
    """Compact one-screen supervisor command center matching the reference layout."""
    theme.supervisor_topbar(_actor_name("Supervisor"), ROLE_LABELS["Supervisor"], notif_count=8)
    core.show_flash()
    tickets = core.tickets()
    active = [t for t in tickets.values() if lc.is_active(t)]
    statuses = {t["ticket_id"]: sla.sla_status(t, NOW) for t in tickets.values()}
    hs = hotspots.detect_hotspots(tickets, NOW)

    total_complaints = sum(t["reports_count"] for t in tickets.values())
    critical = sum(1 for t in active if t["urgency"] == 5)
    breached = sum(1 for t in active if statuses[t["ticket_id"]]["status"] == "BREACHED")
    resolved_week = sum(1 for t in tickets.values() if t["resolved_at"] and (NOW - t["resolved_at"]).days <= 7)
    crew_count = sum(1 for t in active if t["state"] in ("ASSIGNED", "IN PROGRESS"))

    # Compact welcome/header row.
    st.markdown(f"""<div class="cf-sup-welcome"><div><div class="cf-sup-greeting">☀️ <b>Good Evening, {_actor_name("Supervisor")}!</b></div><div class="cf-sup-subtitle">Monitor. Escalate. Ensure resolution. Safer communities, stronger governance.</div></div><div class="cf-sup-quote">📊 &nbsp;“Translate citizen voices into real change.” &nbsp;📖</div></div>""", unsafe_allow_html=True)

    # KPI row.
    stats = st.columns(5, gap="small")
    stat_html = [
        _supervisor_icon_stat("▤", total_complaints, "Total Complaints", "blue", "↑ 12%", "#16A34A"),
        _supervisor_icon_stat("⚠", critical, "Critical Issues", "red", "↑ 31%", "#EF4444"),
        _supervisor_icon_stat("◷", breached, "SLA Breaches", "orange", "↑ 2", "#EF4444"),
        _supervisor_icon_stat("✓", resolved_week, "Resolved This Week", "green", "↑ 43%", "#16A34A"),
        _supervisor_icon_stat("👥", crew_count, "Active Field Crews", "purple"),
    ]
    for col, html in zip(stats, stat_html):
        with col:
            st.markdown(html, unsafe_allow_html=True)

    # ROW 1: heatmap/hotspot + critical tickets, matching the reference screenshot.
    st.markdown('<div class="cf-sup-section-gap"></div>', unsafe_allow_html=True)
    main_left, critical_right = st.columns([2.15, 0.92], gap="small")
    with main_left:
        map_col, hot_col = st.columns([3.25, 1.0], gap="small")
        with map_col:
            st.markdown('<div class="cf-sup-card cf-heatmap-card"><div class="cf-sup-card-head"><div><span class="cf-section-icon blue">◈</span><b>City Issue Heatmap</b></div><div class="cf-map-legend"><span class="active">All</span><span>🔴 Electrical</span><span>🔵 Water</span><span>🟠 Roads</span><span>🟢 Sanitation</span></div><span class="cf-filter">Last 7 days⌄</span></div>', unsafe_allow_html=True)
            geo.render_geo_section(tickets, lambda t: statuses[t["ticket_id"]], [h["ward"] for h in hs if h["status"] == "HOTSPOT"])
            st.markdown('</div>', unsafe_allow_html=True)
        with hot_col:
            hot = hs[0] if hs else None
            hot_ward = hot["ward"] if hot else "Ward 12"
            ward_tickets = [t for t in active if t["ward"] == hot_ward]
            crit = sum(1 for t in ward_tickets if t["urgency"] == 5)
            high = sum(1 for t in ward_tickets if t["urgency"] == 4)
            med = sum(1 for t in ward_tickets if t["urgency"] == 3)
            low = max(0, len(ward_tickets) - crit - high - med)
            st.markdown(f"""<div class="cf-sup-card cf-hotspot-side"><div class="cf-hotspot-title"><b>{hot_ward} (Hotspot)</b></div><div class="cf-hotspot-count">Active complaints <b>{len(ward_tickets)}</b></div><div class="cf-severity"><span>🔴 Critical</span><b>{crit}</b></div><div class="cf-severity"><span>🟠 High</span><b>{high}</b></div><div class="cf-severity"><span>🟡 Medium</span><b>{med}</b></div><div class="cf-severity"><span>🟢 Low</span><b>{low}</b></div></div>""", unsafe_allow_html=True)
            st.button("View Ward Details →", type="primary", use_container_width=True, key="sup_view_ward")
    with critical_right:
        _supervisor_critical_panel(active, statuses)

    # ROW 2: compact analytics cards.
    st.markdown('<div class="cf-sup-section-gap"></div>', unsafe_allow_html=True)
    dept_col, sla_col, ai_col = st.columns([1.42, 1.18, 1.0], gap="small")
    with dept_col:
        _supervisor_department_card(tickets)
    with sla_col:
        _supervisor_sla_card(tickets, NOW)
    with ai_col:
        _supervisor_ai_brief_card(tickets, hs, NOW)

    # ROW 3: compact operational cards.
    st.markdown('<div class="cf-sup-section-gap"></div>', unsafe_allow_html=True)
    esc_col, activity_col, quick_col = st.columns([1.52, 1.0, 1.0], gap="small")
    with esc_col:
        _supervisor_escalation_table(active, statuses)
    with activity_col:
        _supervisor_recent_activity(tickets)
    with quick_col:
        _supervisor_quick_actions()

    # Detailed tools remain available without extending the dashboard's default height.
    with st.expander("🔎 Open detailed supervisor tools", expanded=False):
        _priority_brief_section(tickets, hs, NOW)
        render_hotspots(hs)
        _analytics_section(tickets, NOW)
        render_command_center("Supervisor", NOW)
        render_registry(NOW)

def render_view(role, NOW):
    if role == "Citizen":
        render_citizen(NOW)
    elif role == "Supervisor":
        render_supervisor(NOW)
    else:
        render_officer(role, NOW)