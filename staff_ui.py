"""staff_ui.py — compact one-screen dashboards + working pages for
Supervisor, Municipal Officer and Field Technician. Every existing feature is kept
(command center, evidence, Cedar details, analytics, priority brief, hotspots, registry, audit log)."""
import pandas as pd
import streamlit as st

import ai_insights
import cedar_eval
import core
import geo_intel as geo
import hotspots
import layout
import lifecycle as lc
import opensearch_search as search
import sla_escalation as sla
import views

ss = st.session_state

PAGES = {
    "Supervisor": [("Dashboard", "🏠"), ("All Tickets", "🎫"), ("Escalations", "🚨"), ("Team Management", "👥"),
                   ("Ward Analytics", "📊"), ("City Map & Hotspots", "🗺️"), ("Approvals", "✅"),
                   ("Reports", "📑"), ("Policy & Authorization", "🔐"), ("Notifications", "🔔")],
    "MunicipalOfficer": [("Dashboard", "🏠"), ("Ticket Center", "🎟️"), ("Approvals", "✅"),
                         ("City Map & Hotspots", "🗺️"), ("Analytics", "📊"), ("Registry & Audit", "📜"),
                         ("Notifications", "🔔")],
    "FieldTechnician": [("My Crew Queue", "🔧"), ("Ticket Center", "🎟️"), ("Map", "🗺️"),
                        ("Notifications", "🔔")],
}
TICKET_PAGE = {"Supervisor": "All Tickets", "MunicipalOfficer": "Ticket Center", "FieldTechnician": "Ticket Center"}
MAP_PAGE = {"Supervisor": "City Map & Hotspots", "MunicipalOfficer": "City Map & Hotspots", "FieldTechnician": "Map"}
QUICK = {
    "Supervisor": [("✓ Approve Requests", "Approvals"), ("↗ Reassign Ticket", "Team Management"),
                   ("➤ Send Notification", "Notifications"), ("📑 Generate Report", "Reports")],
    "MunicipalOfficer": [("✓ Approvals", "Approvals"), ("🎟️ Ticket Center", "Ticket Center"),
                         ("🗺️ Map", "City Map & Hotspots"), ("📜 Registry", "Registry & Audit")],
    "FieldTechnician": [("🔧 My Queue", "My Crew Queue"), ("🎟️ Ticket Center", "Ticket Center"),
                        ("🗺️ Map", "Map"), ("🔔 Alerts", "Notifications")],
}


# ------------------------------------------------------------ helpers
def badges(role, NOW):
    ts = [t for t in core.tickets().values() if lc.is_active(t)]
    out = {"Notifications": len(layout.notifications(role, NOW))}
    if role != "FieldTechnician":
        out["Approvals"] = sum(1 for t in ts if t["state"] == "AWAITING APPROVAL"
                               or (t["state"] == "ASSIGNED" and t["urgency"] >= 4))
        out["Escalations"] = sum(1 for t in ts if t["escalation_level"] >= 1
                                 or sla.sla_status(t, NOW)["status"] in ("AT RISK", "BREACHED"))
    return out


def _open(tid, role):
    ss["selected_ticket"] = tid
    layout.goto(TICKET_PAGE[role])


def _ward_details(ward, role):
    ss["geo_ward"] = ward
    layout.goto(MAP_PAGE[role])


def _head(icon, title, cls="blue"):
    st.markdown(f'<div class="cf-sup-card-head"><div><span class="cf-section-icon {cls}">{layout.svg(icon, 15)}</span>'
                f'<b>{title}</b></div></div>', unsafe_allow_html=True)


def _greeting(role, sub):
    h = core.now().hour
    part = "Morning" if h < 12 else "Afternoon" if h < 17 else "Evening"
    quote = {"Supervisor": "Translate citizen voices into real change.",
             "MunicipalOfficer": "Approve fast. Allocate wisely. Serve well.",
             "FieldTechnician": "On the ground. In action."}[role]
    st.markdown(
        f'<div class="cf-sup-welcome"><div><div class="cf-sup-greeting">{"☀️" if h < 17 else "🌙"} '
        f'Good {part}, {layout.DEMO_NAMES[role].split()[0]}!</div><div class="cf-sup-subtitle">{sub}</div></div>'
        f'<div class="cf-sup-quote">“{quote}”</div></div>', unsafe_allow_html=True)


def _kpis(items):
    for col, (icon, val, label, color) in zip(st.columns(len(items), gap="small"), items):
        col.markdown(layout.stat_card(icon, val, label, color), unsafe_allow_html=True)


def _statuses(NOW):
    return {t["ticket_id"]: sla.sla_status(t, NOW) for t in core.tickets().values()}


# ------------------------------------------------------------ cards
def _map_card(role, tickets, hs, height=240, side=True):
    df = geo.tickets_dataframe(tickets)
    hot = [h["ward"] for h in hs if h["status"] == "HOTSPOT"]
    with st.container(border=True):
        _head("◈", "City Issue Heatmap")
        if df.empty:
            st.info("No active complaints on the map.")
            return
        clusters = geo.ward_clusters(df, hot)
        wards = clusters.sort_values("complaints", ascending=False)["ward"].tolist()
        if ss.get("cmp_ward") not in wards:
            ss["cmp_ward"] = next((w for w in hot if w in wards), wards[0])
        deck = geo.build_deck(df, clusters, True, True, True)
        if side:
            mcol, pcol = st.columns([2.6, 1.15], gap="small")
        else:
            mcol = pcol = st.container()
        with mcol:
            try:
                ev = st.pydeck_chart(deck, use_container_width=True, height=height, on_select="rerun",
                                     selection_mode="single-object", key="cmp_map")
                clicked = geo._clicked_ward(ev)
                if clicked and clicked != ss.get("_cmp_click") and clicked in wards:
                    ss["cmp_ward"] = clicked
                ss["_cmp_click"] = clicked
            except TypeError:
                st.pydeck_chart(deck, use_container_width=True, height=height)
        with pcol:
            ward = st.selectbox("Ward", wards, key="cmp_ward", label_visibility="collapsed")
            sub = [t for t in tickets.values() if lc.is_active(t) and t["ward"] == ward]
            n = lambda lo, hi: sum(t["reports_count"] for t in sub if lo <= t["urgency"] <= hi)
            tag = " (Hotspot)" if ward in hot else ""
            rows = "".join(f'<div class="cf-severity"><span>{lab}</span><b>{v}</b></div>' for lab, v in
                           (("🔴 Critical", n(5, 5)), ("🟠 High", n(4, 4)), ("🟡 Medium", n(3, 3)), ("🟢 Low", n(1, 2))))
            st.markdown(f'<div class="cf-hotspot-title"><b>{ward}{tag}</b></div>'
                        f'<div class="cf-hotspot-count">Active complaints <b>{n(1, 5)}</b></div>{rows}',
                        unsafe_allow_html=True)
            st.button("View Ward Details →", type="primary", use_container_width=True, key="cmp_ward_btn",
                      on_click=_ward_details, args=(ward, role))


def _critical_card(role, active, statuses, limit=4):
    crit = sorted([t for t in active if t["urgency"] >= 4
                   or statuses[t["ticket_id"]]["status"] in ("AT RISK", "BREACHED")],
                  key=lambda t: (-int(statuses[t["ticket_id"]]["status"] == "BREACHED"), -t["urgency"],
                                 -statuses[t["ticket_id"]]["pct"]))[:limit]
    with st.container(border=True):
        _head("⚠", "Critical &amp; Escalated Tickets", "red")
        if not crit:
            st.success("No critical or escalated tickets right now.")
        for t in crit:
            s = statuses[t["ticket_id"]]
            if s["status"] == "BREACHED":
                stat, act = "SLA BREACHED", "Review"
            elif s["status"] == "AT RISK":
                stat, act = f"SLA risk: {sla.fmt_duration(s['remaining'])}", "Take Action"
            else:
                stat, act = ("Escalated" if t["escalation_level"] else "Open"), "View"
            dot, urg = ("red", "Critical") if t["urgency"] == 5 else ("orange", "High")
            a, b = st.columns([3.2, 1.1], gap="small")
            a.markdown(f'<div class="cf-critical-main"><div><b>{t["ticket_id"]}</b> <span class="cf-dot {dot}"></span>'
                       f'{urg}<span class="cf-critical-status">{stat}</span></div>'
                       f'<div class="cf-critical-title">{t["title"]}</div>'
                       f'<div class="cf-critical-meta">{t["ward"]} · {t["category"]}</div></div>',
                       unsafe_allow_html=True)
            b.button(act, key=f"crit_{t['ticket_id']}", on_click=_open, args=(t["ticket_id"], role),
                     use_container_width=True)


def _dept_card(tickets):
    counts = {}
    for t in tickets.values():
        lab = geo.dept_style(t["category"])[0]
        counts[lab] = counts.get(lab, 0) + t["reports_count"]
    items = sorted(counts.items(), key=lambda x: -x[1])[:5]
    mx = max((v for _, v in items), default=1)
    cls = ["pink", "blue", "yellow", "green", "purple"]
    rows = "".join(f'<div class="cf-bar-row"><span>{n}</span><div class="cf-bar"><i class="{cls[i % 5]}" '
                   f'style="width:{max(8, int(v / mx * 100))}%"></i></div><b>{v}</b></div>'
                   for i, (n, v) in enumerate(items))
    with st.container(border=True):
        _head("▤", "Department-wise Tickets", "purple")
        st.markdown(rows, unsafe_allow_html=True)


def _sla_card(tickets, NOW):
    done = [t for t in tickets.values() if not lc.is_active(t)]
    met = sum(1 for t in done if sla.sla_status(t, NOW)["status"] == "MET")
    on_time = round(met / len(done) * 100) if done else 100
    act = [sla.sla_status(t, NOW)["status"] for t in tickets.values() if lc.is_active(t)]
    n = max(1, len(act))
    risk, br = round(act.count("AT RISK") / n * 100), round(act.count("BREACHED") / n * 100)
    with st.container(border=True):
        _head("✓", "SLA Compliance", "green")
        st.markdown(
            f'<div class="cf-sla-body"><div class="cf-donut" style="--pct:{on_time * 3.6}deg"><div><b>{on_time}%</b>'
            f'<span>On Time</span></div></div><div class="cf-sla-legend">'
            f'<div><i class="green"></i>On Time (closed) <b>{on_time}%</b></div>'
            f'<div><i class="orange"></i>At Risk (active) <b>{risk}%</b></div>'
            f'<div><i class="red"></i>Breached (active) <b>{br}%</b></div></div></div>', unsafe_allow_html=True)


def _brief_card(tickets, hs, NOW):
    try:
        brief = ai_insights.generate_priority_brief(tickets, hs, NOW)
    except Exception:
        brief = []
    with st.container(border=True):
        _head("✦", "AI Priority Brief", "purple")
        for i, b in enumerate(brief[:3], 1):
            txt = b["recommendation"]
            txt = txt[:105] + "…" if len(txt) > 105 else txt
            st.markdown(f'<div class="cf-ai-line"><span>{i}</span><p><b>{b["ward"]} · {b["department"]}</b><br>{txt}</p></div>',
                        unsafe_allow_html=True)
        if not brief:
            st.caption("Nothing urgent — all wards look calm.")
        st.button("Full brief →", key="brief_more", on_click=layout.goto, args=("Reports" if ss["actor_role"] == "Supervisor"
                                                                                   else TICKET_PAGE[ss["actor_role"]],))


def _escalation_card(role, active, statuses):
    rows = []
    for t in sorted(active, key=lambda x: -statuses[x["ticket_id"]]["pct"]):
        s = statuses[t["ticket_id"]]
        if t["escalation_level"] >= 1 or t["reopen_count"] or s["status"] in ("AT RISK", "BREACHED"):
            lvl = t["escalation_level"]
            rows.append({"Ticket": t["ticket_id"], "Issue": t["title"][:26],
                         "Now with": sla.CHAIN_LABELS[sla.CHAIN[lvl]],
                         "Next": sla.CHAIN_LABELS[sla.CHAIN[min(lvl + 1, 2)]],
                         "Reason": "Citizen dispute" if t["reopen_count"] else
                                   "SLA breach" if s["status"] == "BREACHED" else
                                   "SLA risk" if s["status"] == "AT RISK" else "Escalated",
                         "Time": s["message"].split(" — ")[0]})
    with st.container(border=True):
        _head("↥", "Escalation Queue", "orange")
        if rows:
            st.dataframe(pd.DataFrame(rows[:8]), use_container_width=True, hide_index=True, height=150)
        else:
            st.caption("No active escalations.")


def _activity_card(tickets):
    ev = sorted(((h["at"], t["ticket_id"], h) for t in tickets.values() for h in t["history"][-2:]),
                key=lambda x: x[0], reverse=True)[:5]
    rows = "".join(f'<div class="cf-activity-row"><span class="cf-activity-time">{at:%H:%M}</span>'
                   f'<span class="cf-activity-dot"></span><span>{tid} · {lc.STATE_LABELS.get(h["state"], h["state"])}'
                   f' · {h["actor"]}</span></div>' for at, tid, h in ev)
    with st.container(border=True):
        _head("◷", "Recent Activity", "purple")
        st.markdown(rows or "No recent activity.", unsafe_allow_html=True)


def _quick_card(role):
    with st.container(border=True):
        _head("⚙", "Quick Actions", "navy")
        items = QUICK[role]
        for row in (items[:2], items[2:]):
            for col, (label, page) in zip(st.columns(2, gap="small"), row):
                col.button(label, key=f"qa_{role}_{page}", on_click=layout.goto, args=(page,),
                           use_container_width=True)


# ------------------------------------------------------------ dashboards
def supervisor_dashboard(NOW):
    tickets = core.tickets()
    active = [t for t in tickets.values() if lc.is_active(t)]
    stt = _statuses(NOW)
    hs = hotspots.detect_hotspots(tickets, NOW)
    _greeting("Supervisor", "Monitor. Escalate. Ensure resolution. Safer communities, stronger governance.")
    _kpis([("▤", sum(t["reports_count"] for t in tickets.values()), "Total Complaints", "blue"),
           ("⚠", sum(1 for t in active if t["urgency"] == 5), "Critical Issues", "red"),
           ("◷", sum(1 for t in active if stt[t["ticket_id"]]["status"] == "BREACHED"), "SLA Breaches", "orange"),
           ("✓", sum(1 for t in tickets.values() if t["resolved_at"] and (NOW - t["resolved_at"]).days <= 7),
            "Resolved This Week", "green"),
           ("👥", len({t["team"] for t in active if t["state"] in ("ASSIGNED", "IN PROGRESS")}),
            "Active Field Crews", "purple")])
    l, r = st.columns([2.15, 0.95], gap="small")
    with l:
        _map_card("Supervisor", tickets, hs, height=235)
    with r:
        _critical_card("Supervisor", active, stt)
    a, b, c = st.columns([1.3, 1.1, 1.1], gap="small")
    with a:
        _dept_card(tickets)
    with b:
        _sla_card(tickets, NOW)
    with c:
        _brief_card(tickets, hs, NOW)
    d, e, f = st.columns([1.5, 1.0, 1.0], gap="small")
    with d:
        _escalation_card("Supervisor", active, stt)
    with e:
        _activity_card(tickets)
    with f:
        _quick_card("Supervisor")


def ops_dashboard(role, NOW):
    crew = role == "FieldTechnician"
    tickets = core.tickets()
    active = [t for t in tickets.values() if lc.is_active(t)]
    if crew:
        active = [t for t in active if t["state"] in ("ASSIGNED", "IN PROGRESS")]
    stt = _statuses(NOW)
    hs = hotspots.detect_hotspots(tickets, NOW)
    _greeting(role, "On the ground. In action. Your assigned work, prioritised by SLA." if crew
              else "Approve, allocate, monitor. Everything assigned to you, prioritised by SLA.")
    n = lambda f: sum(1 for t in active if f(t["urgency"]))
    _kpis([("🔴", n(lambda u: u == 5), "Critical", "red"), ("🟠", n(lambda u: u == 4), "High", "orange"),
           ("🟡", n(lambda u: u == 3), "Medium", "purple"), ("🟢", n(lambda u: u <= 2), "Low", "green"),
           ("⏳", sum(1 for t in active if stt[t["ticket_id"]]["status"] in ("AT RISK", "BREACHED")),
            "SLA at risk", "blue")])
    l, r = st.columns([1.55, 1.2], gap="small")
    with l:
        with st.container(border=True):
            _head("🎫", "Your crew queue" if crew else "Assigned to you", "blue")
            waiting = [t for t in active if t["state"] == "AWAITING APPROVAL"]
            if waiting and not crew:
                st.button(f"📝 {len(waiting)} resolution(s) awaiting approval →", key="ops_wait",
                          on_click=layout.goto, args=("Approvals",))
            if not active:
                st.success("Nothing in your queue. 🎉")
            with st.container(height=255):
                for t in sorted(active, key=lambda t: -stt[t["ticket_id"]]["pct"]):
                    c = st.columns([0.9, 0.95, 2.6, 1.1, 1.9, 0.7], gap="small")
                    c[0].markdown(f"**{t['ticket_id']}**")
                    c[1].markdown(core.BADGES[t["urgency"]])
                    c[2].markdown(f"{t['title']}  \n<span style='color:#9CA3AF;font-size:11px;'>{t['ward']} · "
                                  f"{t['category']}</span>", unsafe_allow_html=True)
                    c[3].markdown(lc.STATE_LABELS[t["state"]])
                    c[4].markdown(stt[t["ticket_id"]]["message"])
                    c[5].button("Open", key=f"q_{t['ticket_id']}", on_click=_open, args=(t["ticket_id"], role))
    with r:
        _map_card(role, tickets, hs, height=200, side=False)
    a, b, c, d = st.columns([1, 1.3, 1, 1], gap="small")
    with a:
        _sla_card(tickets, NOW)
    with b:
        _brief_card(tickets, hs, NOW)
    with c:
        _activity_card(tickets)
    with d:
        _quick_card(role)


# ------------------------------------------------------------ pages
def _registry_rows(NOW):
    rows = []
    for t in core.tickets().values():
        s = sla.sla_status(t, NOW)
        rows.append({"Ticket ID": t["ticket_id"], "Department": t["category"], "Ward": t["ward"],
                     "Priority": t["priority_label"], "State": lc.STATE_LABELS[t["state"]], "SLA": s["status"],
                     "Language": t.get("language", "English"),
                     "Escalated To": sla.CHAIN_LABELS[sla.CHAIN[t["escalation_level"]]],
                     "Reports": t["reports_count"], "Re-opened": t["reopen_count"]})
    return rows


def _tickets_page(role, NOW):
    if role == "Supervisor":
        t1, t2 = st.tabs(["🎟️ Ticket Command Center", "📊 Registry & Audit Log"])
        with t1:
            views.render_command_center(role, NOW)
        with t2:
            views.render_registry(NOW)
    else:
        views.render_command_center(role, NOW)


def _escalations_page(role, NOW):
    st.subheader("🚨 Escalations")
    stt = _statuses(NOW)
    active = [t for t in core.tickets().values() if lc.is_active(t)]
    m = st.columns(3)
    m[0].metric("Breached", sum(1 for t in active if stt[t["ticket_id"]]["status"] == "BREACHED"))
    m[1].metric("At risk", sum(1 for t in active if stt[t["ticket_id"]]["status"] == "AT RISK"))
    m[2].metric("Escalated to Supervisor", sum(1 for t in active if t["escalation_level"] >= 2))
    shown = 0
    for t in sorted(active, key=lambda t: -stt[t["ticket_id"]]["pct"]):
        rep = sla.build_escalation_report(t, stt[t["ticket_id"]])
        if not rep:
            continue
        shown += 1
        with st.expander(f"{t['ticket_id']} · {t['title']} — {stt[t['ticket_id']]['message']}"):
            st.markdown("**Reasons:**\n" + "\n".join(f"- {r}" for r in rep["reasons"]))
            st.info(f"**Recommended:** {rep['action']}")
            st.button("Open in command center", key=f"esc_{t['ticket_id']}", on_click=_open, args=(t["ticket_id"], role))
    if not shown:
        st.success("No escalations recommended right now.")


def _team_page(role, NOW):
    st.subheader("👥 Team Management")
    tickets = core.tickets()
    stt = _statuses(NOW)
    teams = sorted({t["team"] for t in tickets.values()} | {v[0] for v in core.DEPT_DEFAULTS.values()})
    rows = []
    for tm in teams:
        mine = [t for t in tickets.values() if t["team"] == tm and lc.is_active(t)]
        rows.append({"Team": tm, "Active": len(mine), "In progress": sum(1 for t in mine if t["state"] == "IN PROGRESS"),
                     "Critical": sum(1 for t in mine if t["urgency"] >= 4),
                     "SLA breached": sum(1 for t in mine if stt[t["ticket_id"]]["status"] == "BREACHED")})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with st.container(border=True):
        st.markdown("**↗ Reassign a ticket**")
        act = [t["ticket_id"] for t in tickets.values() if lc.is_active(t)]
        c1, c2, c3 = st.columns([1.2, 2, 0.8])
        tid = c1.selectbox("Ticket", act, key="re_tid")
        new = c2.selectbox("Move to team", teams, key="re_team")
        c3.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if c3.button("Reassign", type="primary", use_container_width=True) and tid:
            t = tickets[tid]
            old, t["team"] = t["team"], new
            lc.add_note(t, layout.ROLE_LABELS[role], NOW, f"Reassigned {old} → {new}")
            core.log_event(t, role, f"Reassigned to {new}", "ALLOWED")
            core.flash("success", f"✅ {tid} reassigned to {new}.")
            st.rerun()


def _approvals_page(role, NOW):
    st.subheader("✅ Approvals")
    act = [t for t in core.tickets().values() if lc.is_active(t)]
    st.markdown("##### 🚒 High-urgency dispatches awaiting authorization")
    pend = [t for t in act if t["state"] == "ASSIGNED" and t["urgency"] >= 4]
    if not pend:
        st.caption("No dispatches waiting.")
    for t in pend:
        with st.container(border=True):
            a, b = st.columns([4, 1])
            a.markdown(f"**{t['ticket_id']}** · {core.BADGES[t['urgency']]} · {t['title']}  \n"
                       f"{t['ward']} · {t['team']} · est. {core.inr(t['dispatch_cost'])}")
            if b.button("🚒 Dispatch", key=f"ap_d_{t['ticket_id']}", type="primary", use_container_width=True):
                core.dispatch_crew(t, role)
                st.rerun()
    st.markdown("##### 📝 Resolutions awaiting approval")
    wait = [t for t in act if t["state"] == "AWAITING APPROVAL"]
    if not wait:
        st.caption("No resolutions waiting.")
    for t in wait:
        with st.container(border=True):
            a, b = st.columns([4, 1])
            a.markdown(f"**{t['ticket_id']}** · {t['title']} · {t['ward']}")
            action = next((x for x in lc.available_actions(t) if x.target == "RESOLVED"), None)
            if action and b.button("✅ Approve", key=f"ap_r_{t['ticket_id']}", type="primary", use_container_width=True):
                core.do_step(t, action, role)
                st.rerun()
            if t.get("resolution"):
                with st.expander("View evidence"):
                    views._show_resolution(t)


def _policy_page(role, NOW):
    st.subheader("🔐 Policy & Authorization")
    t1, t2, t3 = st.tabs(["Decision log", "Simulator", "policies.cedar"])
    with t1:
        rows = [{"Time": d["at"].strftime("%d %b %H:%M"), "Ticket": d["resource"], "Principal": d["principal"],
                 "Decision": d["decision"], "Cost": core.inr(d["cost"]), "Policy": d["policy"], "Reason": d["reason"]}
                for t in core.tickets().values() for d in t["authz"]]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No dispatch decisions yet.")
    with t2:
        tk = core.tickets()
        c1, c2 = st.columns(2)
        r = c1.selectbox("Principal", list(lc.ROLES), key="sim_role")
        tid = c2.selectbox("Ticket", list(tk), key="sim_tid")
        t = tk[tid]
        d = cedar_eval.authorize(r, "ApproveDispatch", {"ticket_id": tid, "category": t["category"],
                                                        "urgency": t["urgency"], "cost": t["dispatch_cost"]})
        (st.success if d["allowed"] else st.error)(f"**{d['decision']}** — {d['reason']}  \n`{d['policy']}` · {d['engine']}")
    with t3:
        try:
            with open(cedar_eval.POLICY_FILE, encoding="utf-8") as f:
                st.code(f.read(), language="text")
        except OSError:
            st.caption("policies.cedar not found.")


def _notifications_page(role, NOW):
    st.subheader("🔔 Notifications")
    if role in lc.OFFICERS:
        with st.form("bc_form", clear_on_submit=True):
            c1, c2 = st.columns([5, 1])
            msg = c1.text_input("Broadcast", label_visibility="collapsed",
                                placeholder="📣 Broadcast to crews & citizens, e.g. Heavy rain — Ward 12 crews on standby")
            if c2.form_submit_button("Send", type="primary", use_container_width=True) and msg.strip():
                ss.setdefault("broadcasts", []).append(f"{layout.DEMO_NAMES[role]}: {msg.strip()}")
                st.rerun()
    items = layout.notifications(role, NOW, limit=40)
    if not items:
        st.success("You're all caught up 🎉")
    for i in items:
        st.markdown(f"- {i}")


def _reports_page(role, NOW):
    st.subheader("📑 Reports")
    df = pd.DataFrame(_registry_rows(NOW))
    st.download_button("⬇️ Download ticket registry (CSV)", df.to_csv(index=False), "civicflow_registry.csv", "text/csv")
    tickets = core.tickets()
    views._priority_brief_section(tickets, hotspots.detect_hotspots(tickets, NOW), NOW)


def _map_page(role, NOW):
    st.subheader("🗺️ City Map & Hotspots")
    tickets = core.tickets()
    hs = hotspots.detect_hotspots(tickets, NOW)
    geo.render_geo_section(tickets, lambda t: sla.sla_status(t, NOW), [h["ward"] for h in hs if h["status"] == "HOTSPOT"])
    views.render_hotspots(hs)


# ------------------------------------------------------------ router
def render_search(role, q, NOW):
    pool = {tid: t for tid, t in core.tickets().items() if role != "Citizen" or "me" in t["reporters"]}
    # Data & Search: routed through OpenSearch when it's up (fuzzy, ranked,
    # also matches ticket history/notes text), and transparently falls back
    # to the original in-memory substring scan when it isn't — see
    # opensearch_search.py. Either way this function's behaviour/signature
    # is unchanged, so nothing else about the search bar had to move.
    hit_ids = search.search_tickets(q, pool)
    hits = [pool[tid] for tid in hit_ids if tid in pool]
    c1, c2 = st.columns([6, 1])
    c1.subheader(f"🔍 {len(hits)} result(s) for “{q}”")
    c2.button("✖ Clear", key="clr_search", on_click=lambda: ss.__setitem__(f"search_{role}", ""),
              use_container_width=True)
    for t in hits[:30]:
        if role == "Citizen":
            views._citizen_card(t)
            continue
        c = st.columns([0.9, 1, 3.2, 1.2, 2.2, 0.8], gap="small")
        c[0].markdown(f"**{t['ticket_id']}**")
        c[1].markdown(core.BADGES[t["urgency"]])
        c[2].markdown(f"{t['title']}  \n<span style='color:#9CA3AF;font-size:11px;'>{t['ward']} · {t['category']}</span>",
                      unsafe_allow_html=True)
        c[3].markdown(lc.STATE_LABELS[t["state"]])
        c[4].markdown(sla.sla_status(t, NOW)["message"])
        c[5].button("Open", key=f"sr_{t['ticket_id']}", on_click=_open, args=(t["ticket_id"], role))


def render(role, NOW):
    layout.marker(f"cf-role-{role.lower()}")
    core.show_flash()
    page = ss.get(layout.page_key(role), PAGES[role][0][0])
    if page in ("Dashboard", "My Crew Queue"):
        supervisor_dashboard(NOW) if role == "Supervisor" else ops_dashboard(role, NOW)
    elif page in ("All Tickets", "Ticket Center"):
        _tickets_page(role, NOW)
    elif page == "Escalations":
        _escalations_page(role, NOW)
    elif page == "Team Management":
        _team_page(role, NOW)
    elif page in ("Ward Analytics", "Analytics"):
        views._analytics_section(core.tickets(), NOW)
    elif page in ("City Map & Hotspots", "Map"):
        _map_page(role, NOW)
    elif page == "Approvals":
        _approvals_page(role, NOW)
    elif page == "Reports":
        _reports_page(role, NOW)
    elif page == "Registry & Audit":
        views.render_registry(NOW)
    elif page == "Policy & Authorization":
        _policy_page(role, NOW)
    elif page == "Notifications":
        _notifications_page(role, NOW)