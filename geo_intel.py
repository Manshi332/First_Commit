# geo_intel.py
"""Geospatial intelligence: heatmap, department markers, ward clusters, drill-down."""
import hashlib

import pandas as pd
import pydeck as pdk
import streamlit as st

import lifecycle as lc

DEPT_ORDER = [("Electrical", "🔴"), ("Water", "🟠"), ("Roads", "🟡"), ("Sanitation", "🔵")]
DEPT_STYLE = {
    "electr": ("Electrical", [220, 38, 38, 210]),
    "water": ("Water", [249, 115, 22, 210]),
    "road": ("Roads", [234, 179, 8, 210]),
    "sanit": ("Sanitation", [37, 99, 235, 210]),
}


def dept_style(category: str):
    c = category.lower()
    for key, val in DEPT_STYLE.items():
        if key in c:
            return val
    return ("Other", [107, 114, 128, 210])


def jitter(lat, lon, key, spread=0.006):
    """Deterministic offset so tickets in one locality don't stack on one pixel."""
    h = hashlib.md5(key.encode()).digest()
    return (lat + (h[0] / 255 - 0.5) * 2 * spread,
            lon + (h[1] / 255 - 0.5) * 2 * spread)


def tickets_dataframe(tickets: dict) -> pd.DataFrame:
    rows = []
    for t in tickets.values():
        if not lc.is_active(t):
            continue
        label, color = dept_style(t["category"])
        rows.append({
            "ticket_id": t["ticket_id"], "lat": t["lat"], "lon": t["lon"],
            "dept": label, "color": color, "reports": int(t["reports_count"]),
            "ward": t["ward"], "urgency": int(t["urgency"]), "state": t["state"],
            "radius": 60 + 20 * min(int(t["reports_count"]), 15),
            "tooltip": (f"{t['ticket_id']} · {label} · {t['reports_count']} report(s) · "
                        f"urgency {t['urgency']}/5 · {lc.STATE_LABELS[t['state']]}"),
        })
    return pd.DataFrame(rows)


def ward_clusters(df: pd.DataFrame, hotspot_wards=()) -> pd.DataFrame:
    g = df.groupby("ward").agg(
        lat=("lat", "mean"), lon=("lon", "mean"),
        complaints=("reports", "sum"), tickets=("ticket_id", "count"),
        max_urgency=("urgency", "max"),
    ).reset_index()
    g["label"] = g["complaints"].astype(str)
    g["radius"] = 250 + 25 * g["complaints"].clip(upper=40)
    g["hot"] = g["ward"].isin(set(hotspot_wards))
    g["line"] = g["hot"].apply(lambda h: [239, 68, 68, 255] if h else [255, 255, 255, 230])
    g["tooltip"] = g.apply(
        lambda r: f"{r['ward']} · {int(r['complaints'])} active complaints · {int(r['tickets'])} tickets"
                  + (" · 🔥 AI hotspot" if r["hot"] else ""), axis=1)
    return g


def build_deck(df, clusters, show_heat, show_points, show_clusters):
    layers = []
    if show_heat:
        layers.append(pdk.Layer(
            "HeatmapLayer", id="heat", data=df, get_position="[lon, lat]",
            get_weight="reports", radius_pixels=70, opacity=0.65))
    if show_clusters:
        layers.append(pdk.Layer(
            "ScatterplotLayer", id="clusters", data=clusters, pickable=True,
            get_position="[lon, lat]", get_radius="radius",
            radius_min_pixels=18, radius_max_pixels=46,
            get_fill_color=[30, 41, 59, 175], get_line_color="line",
            stroked=True, line_width_min_pixels=4))
    if show_points:
        layers.append(pdk.Layer(
            "ScatterplotLayer", id="issues", data=df, pickable=True,
            get_position="[lon, lat]", get_radius="radius",
            radius_min_pixels=5, radius_max_pixels=14, get_fill_color="color"))
    if show_clusters:
        layers.append(pdk.Layer(
            "TextLayer", id="cluster_labels", data=clusters, pickable=False,
            get_position="[lon, lat]", get_text="label", get_size=16,
            get_color=[255, 255, 255, 255],
            get_alignment_baseline='"center"', get_text_anchor='"middle"'))
    view = pdk.ViewState(latitude=float(df["lat"].mean()), longitude=float(df["lon"].mean()),
                         zoom=10.5, pitch=0)
    return pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{tooltip}"})


def _clicked_ward(event):
    """Pull a ward name out of a pydeck selection event (None if unsupported/empty)."""
    try:
        objs = (event.selection.get("objects") or {})
        for layer in ("clusters", "issues"):
            if objs.get(layer):
                return objs[layer][0].get("ward")
    except Exception:
        pass
    return None


def render_geo_section(tickets: dict, sla_fn, hotspot_wards=()):
    ss = st.session_state
    st.subheader("🗺️ Hyper-Local Situational Awareness")
    df = tickets_dataframe(tickets)
    if df.empty:
        st.info("No active complaints on the map.")
        return

    t1, t2, t3 = st.columns(3)
    show_heat = t1.checkbox("🔥 Heatmap", True)
    show_clusters = t2.checkbox("⭕ Ward clusters", True)
    show_points = t3.checkbox("📍 Issue markers", True)
    st.caption("🔴 Electrical   🟠 Water   🟡 Roads   🔵 Sanitation   ·   "
               "cluster number = active citizen complaints in that ward   ·   red ring = 🔥 AI hotspot")

    clusters = ward_clusters(df, hotspot_wards)
    wards = clusters.sort_values("complaints", ascending=False)["ward"].tolist()
    left, right = st.columns([3, 2])

    with left:
        deck = build_deck(df, clusters, show_heat, show_points, show_clusters)
        try:
            event = st.pydeck_chart(deck, use_container_width=True, on_select="rerun",
                                    selection_mode="single-object", key="civic_map")
            clicked = _clicked_ward(event)
            if clicked and clicked != ss.get("_last_map_click"):
                ss["geo_ward"] = clicked
            ss["_last_map_click"] = clicked
        except TypeError:   # older Streamlit without map selection support
            st.pydeck_chart(deck, use_container_width=True)

    with right:
        if ss.get("geo_ward") not in wards:
            ss["geo_ward"] = wards[0]
        ward = st.selectbox("Inspect ward (or click a cluster on the map)", wards, key="geo_ward")
        sub = df[df["ward"] == ward]
        counts = sub.groupby("dept")["reports"].sum()
        st.markdown(f"### {ward}")
        m1, m2 = st.columns(2)
        m1.metric("Active complaints", int(sub["reports"].sum()))
        m2.metric("Active tickets", len(sub))
        for label, emoji in DEPT_ORDER:
            st.markdown(f"{emoji} **{label}:** {int(counts.get(label, 0))}")
        rows = []
        for tid in sub["ticket_id"]:
            t = tickets[tid]
            rows.append({"Ticket": tid, "Dept": dept_style(t["category"])[0],
                         "Reports": t["reports_count"], "Urgency": t["urgency"],
                         "State": lc.STATE_LABELS[t["state"]], "SLA": sla_fn(t)["status"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)