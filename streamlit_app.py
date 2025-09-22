# streamlit_app.py
"""
Streamlit UI for Flight Path Optimizer (medium version).
Now with session_state so results persist after reruns.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components

# import utilities from your project
from flight_utils import great_circle_points, haversine_km, bearing_between
from wind_fetcher import get_current_wind, tailwind_component_kmh

# optional optimizer
try:
    import optimize
    HAS_OPTIMIZE = True
except Exception:
    HAS_OPTIMIZE = False

# --------- Config ----------
AIRPORTS_CSV = Path("data/airports.csv")
DEFAULT_ORIGIN = "KJFK"
DEFAULT_DEST = "EGLL"

# --------- Helpers ----------
@st.cache_data
def load_airports(csv_path=AIRPORTS_CSV):
    return pd.read_csv(csv_path, low_memory=False)

def find_airport(df, code: str):
    code_up = str(code).upper().strip()
    if "ident" in df.columns:
        r = df[df["ident"].fillna("").str.upper() == code_up]
        if not r.empty:
            return r.iloc[0]
    for col in ["iata_code", "iata", "icao_code", "gps_code"]:
        if col in df.columns:
            r = df[df[col].fillna("").str.upper() == code_up]
            if not r.empty:
                return r.iloc[0]
    return None

def compute_wind_adjusted_time_hours(points, cruise_kmh, sample_rate=8, verify_ssl=True):
    total_hours = 0.0
    wind_cache = {}
    for i in range(len(points)-1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i+1]
        seg_km = haversine_km(lat1, lon1, lat2, lon2)
        bearing = bearing_between(lat1, lon1, lat2, lon2)
        mid_lat = (lat1 + lat2) / 2.0
        mid_lon = (lon1 + lon2) / 2.0
        key = (round(mid_lat, 4), round(mid_lon, 4))
        if (i % sample_rate) == 0:
            try:
                w = get_current_wind(mid_lat, mid_lon, verify_ssl=verify_ssl)
            except Exception:
                w = {"windspeed_kmh": 0.0, "winddirection_deg": 0.0}
            wind_cache[key] = w
        w = wind_cache.get(key, {"windspeed_kmh": 0.0, "winddirection_deg": 0.0})
        tail_kmh = tailwind_component_kmh(w["windspeed_kmh"], w["winddirection_deg"], bearing)
        ground_speed = max(40.0, cruise_kmh + tail_kmh)
        total_hours += seg_km / ground_speed
    return total_hours

def build_folium_map(origin, dest, points, naive_hours, wind_hours=None):
    mid_lat = sum(p[0] for p in points) / len(points)
    mid_lon = sum(p[1] for p in points) / len(points)
    m = folium.Map(location=(mid_lat, mid_lon), zoom_start=4, tiles="OpenStreetMap")

    folium.Marker([origin["latitude_deg"], origin["longitude_deg"]], tooltip="Origin").add_to(m)
    folium.Marker([dest["latitude_deg"], dest["longitude_deg"]], tooltip="Destination").add_to(m)
    folium.PolyLine(points, color="blue", weight=3, opacity=0.8).add_to(m)

    total_km = sum(haversine_km(points[i][0], points[i][1],
                                points[i+1][0], points[i+1][1]) for i in range(len(points)-1))
    html = f"<div style='background:white;padding:8px;border-radius:8px;'>"
    html += f"<b>Distance:</b> {total_km:.1f} km<br>"
    html += f"<b>Naive ETA:</b> {naive_hours:.2f} h<br>"
    if wind_hours:
        html += f"<b>Wind-adjusted ETA:</b> {wind_hours:.2f} h<br>"
    html += "</div>"
    folium.map.Marker((mid_lat, mid_lon), icon=folium.DivIcon(html=html)).add_to(m)
    return m

# --------- Streamlit UI ----------
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")
st.title("✈️ Flight Path Optimizer")

df_airports = load_airports()

# session state init
if "results" not in st.session_state:
    st.session_state["results"] = None

col1, col2, col3 = st.columns(3)
with col1:
    origin_input = st.text_input("Origin airport code", value=DEFAULT_ORIGIN)
with col2:
    dest_input = st.text_input("Destination airport code", value=DEFAULT_DEST)
with col3:
    cruise_kmh = st.slider("Cruise speed (km/h)", 600, 1000, 900)

use_wind = st.checkbox("Use wind-adjusted ETA", value=False)
points = st.slider("Points along GC", 50, 600, 200, step=10)
ssl_verify = st.checkbox("Verify SSL for wind API", value=True)

if st.button("Compute route"):
    origin = find_airport(df_airports, origin_input)
    dest = find_airport(df_airports, dest_input)

    if origin is None:
        st.error(f"Origin '{origin_input}' not found.")
    elif dest is None:
        st.error(f"Destination '{dest_input}' not found.")
    else:
        lat1, lon1 = float(origin["latitude_deg"]), float(origin["longitude_deg"])
        lat2, lon2 = float(dest["latitude_deg"]), float(dest["longitude_deg"])

        pts = great_circle_points(lat1, lon1, lat2, lon2, n_points=points)
        total_km = sum(haversine_km(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) for i in range(len(pts)-1))
        naive_h = total_km / cruise_kmh

        wind_h = None
        if use_wind:
            wind_h = compute_wind_adjusted_time_hours(pts, cruise_kmh, verify_ssl=ssl_verify)

        # store results in session state
        st.session_state["results"] = {
            "origin": origin,
            "dest": dest,
            "pts": pts,
            "naive_h": naive_h,
            "wind_h": wind_h,
        }

# ---- Display results if present ----
if st.session_state["results"] is not None:
    r = st.session_state["results"]
    origin, dest, pts, naive_h, wind_h = r["origin"], r["dest"], r["pts"], r["naive_h"], r["wind_h"]

    total_km = sum(haversine_km(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) for i in range(len(pts)-1))
    st.metric("Distance (km)", f"{total_km:.1f}")
    st.metric("Naive ETA", f"{naive_h:.2f} h")
    if wind_h is not None:
        st.metric("Wind-adjusted ETA", f"{wind_h:.2f} h")

    folium_map = build_folium_map(origin, dest, pts, naive_h, wind_hours=wind_h)
    st_folium(folium_map, width=1000, height=700)

    # download option
    html = folium_map.get_root().render()
    st.download_button("Download map HTML", data=html, file_name="route_map.html", mime="text/html")
