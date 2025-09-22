# streamlit_app.py
"""
Streamlit UI for Flight Path Optimizer (medium version).
- Enter origin/destination airport codes (ICAO or IATA)
- Set cruise speed / altitude slider (alt doesn't affect wind in this simple demo)
- Optionally use wind-adjusted ETA and run optimizer (corridor + A* from optimize.py)
- Displays a Folium map inline via streamlit-folium
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import time
import json
import streamlit.components.v1 as components

import folium
from streamlit_folium import st_folium

# import utilities from your project
from flight_utils import great_circle_points, haversine_km, bearing_between
from wind_fetcher import get_current_wind, tailwind_component_kmh

# optional: import optimizer module if you have optimize.py
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
    df = pd.read_csv(csv_path, low_memory=False)
    # normalize columns - be permissive
    return df

def find_airport(df, code: str):
    code_up = str(code).upper().strip()
    # try common columns
    if "ident" in df.columns:
        r = df[df["ident"].fillna("").str.upper() == code_up]
        if not r.empty:
            return r.iloc[0]
    for col in ["iata_code", "iata", "icao_code", "gps_code"]:
        if col in df.columns:
            r = df[df[col].fillna("").str.upper() == code_up]
            if not r.empty:
                return r.iloc[0]
    # fallback substring in name/municipality
    for col in ["name", "municipality"]:
        if col in df.columns:
            r = df[df[col].fillna("").str.upper().str.contains(code_up, na=False)]
            if not r.empty:
                return r.iloc[0]
    return None

def compute_wind_adjusted_time_hours(points, cruise_kmh, sample_rate=8, verify_ssl=True):
    """Sum segment times using local tailwind components. Returns hours (float)."""
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

def build_folium_map(origin, dest, points, naive_hours, wind_hours=None, opt_path=None):
    # center map at midpoint
    mid_lat = sum(p[0] for p in points) / len(points)
    mid_lon = sum(p[1] for p in points) / len(points)
    m = folium.Map(location=(mid_lat, mid_lon), zoom_start=4, tiles="OpenStreetMap")

    folium.Marker(
        [origin["latitude_deg"], origin["longitude_deg"]],
        popup=f"{origin.get('ident','')} - {origin.get('name','')}",
        tooltip="Origin"
    ).add_to(m)

    folium.Marker(
        [dest["latitude_deg"], dest["longitude_deg"]],
        popup=f"{dest.get('ident','')} - {dest.get('name','')}",
        tooltip="Destination"
    ).add_to(m)

    # main great-circle route (blue)
    folium.PolyLine(points, color="blue", weight=3, opacity=0.8, popup="Great-circle route").add_to(m)

    # optional optimized path (green)
    if opt_path:
        folium.PolyLine(opt_path, color="green", weight=3.5, opacity=0.95, popup="Optimized path").add_to(m)

    # stats box
    total_km = sum(haversine_km(points[i][0], points[i][1], points[i+1][0], points[i+1][1]) for i in range(len(points)-1))
    html = f"<div style='background:white;padding:8px;border-radius:8px;'><b>Distance:</b> {total_km:.1f} km<br>"
    html += f"<b>Naive ETA:</b> {naive_hours*60:.0f} min ({naive_hours:.2f} h)<br>"
    if wind_hours is not None:
        html += f"<b>Wind-adjusted ETA:</b> {wind_hours*60:.0f} min ({wind_hours:.2f} h)<br>"
        html += f"<b>Diff:</b> {(wind_hours-naive_hours)*60:.0f} min<br>"
    html += "</div>"
    folium.map.Marker((mid_lat, mid_lon), icon=folium.DivIcon(html=html)).add_to(m)
    return m

# --------- Streamlit UI ----------
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")

st.title("✈️ Flight Path Optimizer — Streamlit demo")
st.markdown("Enter ICAO/IATA codes (or search), choose options, and click **Compute**.")

df_airports = load_airports()

col1, col2, col3 = st.columns([1,1,1])

with col1:
    origin_input = st.text_input("Origin airport code (ICAO or IATA)", value=DEFAULT_ORIGIN)
    if st.button("Search origin by name/code", key="s_orig"):
        search = origin_input.strip()
        matches = df_airports[
            df_airports.apply(lambda r: search.upper() in str(r.get("ident","")).upper() 
                              or search.upper() in str(r.get("iata_code","")).upper()
                              or search.upper() in str(r.get("name","")).upper()
                              or search.upper() in str(r.get("municipality","")).upper(), axis=1)
        ]
        if matches.empty:
            st.info("No results found.")
        else:
            selection = st.selectbox("Pick origin from results", options=[f'{r.get("ident","")}: {r.get("name","")} ({r.get("municipality","")})' for _, r in matches.iterrows()])
            # extract code
            if selection:
                origin_input = selection.split(":")[0]

with col2:
    dest_input = st.text_input("Destination airport code (ICAO or IATA)", value=DEFAULT_DEST)
    if st.button("Search destination by name/code", key="s_dest"):
        search = dest_input.strip()
        matches = df_airports[
            df_airports.apply(lambda r: search.upper() in str(r.get("ident","")).upper() 
                              or search.upper() in str(r.get("iata_code","")).upper()
                              or search.upper() in str(r.get("name","")).upper()
                              or search.upper() in str(r.get("municipality","")).upper(), axis=1)
        ]
        if matches.empty:
            st.info("No results found.")
        else:
            selection = st.selectbox("Pick destination from results", options=[f'{r.get("ident","")}: {r.get("name","")} ({r.get("municipality","")})' for _, r in matches.iterrows()])
            if selection:
                dest_input = selection.split(":")[0]

with col3:
    cruise_kmh = st.slider("Cruise speed (km/h)", min_value=600, max_value=1000, value=900)
    altitude_ft = st.slider("Cruise altitude (ft) — informational", min_value=20000, max_value=43000, value=35000, step=1000)
    use_wind = st.checkbox("Use wind-adjusted ETA", value=False)
    sample_rate = st.slider("Wind sample rate (higher = fewer API calls)", min_value=1, max_value=20, value=8)
    run_optimizer = st.checkbox("Run optimizer (corridor + A*)", value=False)
    if run_optimizer and not HAS_OPTIMIZE:
        st.warning("optimize.py not found or failed to import; optimizer disabled.")
        run_optimizer = False
    ssl_verify = st.checkbox("Verify SSL for wind API (uncheck if you had cert errors)", value=True)
    points = st.slider("Points along GC (visual resolution)", min_value=50, max_value=600, value=200, step=10)

st.divider()
compute = st.button("Compute route")

if compute:
    # find airports
    origin = find_airport(df_airports, origin_input)
    dest = find_airport(df_airports, dest_input)
    if origin is None:
        st.error(f"Origin '{origin_input}' not found in airports CSV.")
    elif dest is None:
        st.error(f"Destination '{dest_input}' not found in airports CSV.")
    else:
        st.success(f"Found origin: {origin.get('name','')} ({origin.get('ident','')})")
        st.success(f"Found destination: {dest.get('name','')} ({dest.get('ident','')})")

        lat1, lon1 = float(origin["latitude_deg"]), float(origin["longitude_deg"])
        lat2, lon2 = float(dest["latitude_deg"]), float(dest["longitude_deg"])

        with st.spinner("Computing great-circle points..."):
            pts = great_circle_points(lat1, lon1, lat2, lon2, n_points=points)
        # distance and naive ETA
        total_km = sum(haversine_km(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) for i in range(len(pts)-1))
        naive_h = total_km / cruise_kmh

        wind_h = None
        if use_wind:
            with st.spinner("Fetching winds and computing wind-adjusted ETA (may take some seconds)..."):
                try:
                    wind_h = compute_wind_adjusted_time_hours(pts, cruise_kmh, sample_rate=sample_rate, verify_ssl=ssl_verify)
                except Exception as e:
                    st.error(f"Wind API failed: {e}. Falling back to no-wind calculation.")
                    wind_h = None

        # show numeric results
        st.metric("Distance (km)", f"{total_km:.1f}")
        st.metric("Naive ETA (hh:mm)", f"{int(naive_h):02d}h {int((naive_h-int(naive_h))*60):02d}m")
        if wind_h is not None:
            st.metric("Wind-adjusted ETA (hh:mm)", f"{int(wind_h):02d}h {int((wind_h-int(wind_h))*60):02d}m")
            delta_min = (wind_h - naive_h) * 60.0
            st.write(f"Difference vs naive: {delta_min:.0f} minutes")

        # if optimizer asked, call optimize.run_optimization and display its saved map
        if run_optimizer and HAS_OPTIMIZE:
            st.info("Running optimizer (this may take ~30s depending on slices & API calls)...")
            try:
                out_path = Path("outputs/streamlit_optimized_map.html")
                # choose reasonable defaults
                res = optimize.run_optimization(origin.get('ident',''), dest.get('ident',''), slices=40, lateral_offsets_km=[-120,0,120], cruise_kmh=cruise_kmh, use_wind=use_wind, verify_ssl=ssl_verify, out=str(out_path))
                # show summary
                st.write("Optimizer results:")
                st.write(f"Great-circle distance: {res['gc_km']:.1f} km")
                st.write(f"Naive ETA: {res['naive_h']*60:.0f} min")
                st.write(f"Optimized ETA: {res['opt_h']*60:.0f} min")
                # embed HTML map (opt uses folium internally and wrote out a file)
                html = out_path.read_text(encoding="utf8")
                components.html(html, height=700, scrolling=True)
                # allow download
                st.download_button("Download optimized map HTML", data=html, file_name="optimized_map.html", mime="text/html")
            except Exception as e:
                st.error(f"Optimizer failed: {e}")
        else:
            # build and show folium map inline
            folium_map = build_folium_map(origin, dest, pts, naive_h, wind_hours=wind_h, opt_path=None)
            st_folium(folium_map, width=1000, height=700)
            # also offer download of the HTML
            html = folium_map.get_root().render()
            st.download_button("Download map HTML", data=html, file_name="route_map.html", mime="text/html")
