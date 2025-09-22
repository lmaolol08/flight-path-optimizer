import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from pyproj import Geod

# ======================
# Load airports
# ======================
@st.cache_data
def load_airports():
    df = pd.read_csv("data/airports.csv", low_memory=False)

    # Normalize IATA column
    if "iata" in df.columns:
        df.rename(columns={"iata": "iata_code"}, inplace=True)

    df = df[df["iata_code"].notna() & (df["iata_code"] != "\\N")]
    df = df.drop_duplicates(subset=["iata_code"])

    # Add display column (city - name (IATA))
    df["display_name"] = (
        df["municipality"].fillna("Unknown") + " – " +
        df["name"].fillna("Unknown") + " (" + df["iata_code"] + ")"
    )

    return df


df_airports = load_airports()
geod = Geod(ellps="WGS84")

# ======================
# Great circle calculator
# ======================
def great_circle_points(lat1, lon1, lat2, lon2, n_points=100):
    # geod.npts returns list of (lon, lat)
    intermediate = geod.npts(lon1, lat1, lon2, lat2, n_points)
    path = [(lat1, lon1)] + [(lat, lon) for lon, lat in intermediate] + [(lat2, lon2)]
    return path


def compute_distance_hours(lat1, lon1, lat2, lon2, speed_kmh):
    az12, az21, dist_m = geod.inv(lon1, lat1, lon2, lat2)
    dist_km = dist_m / 1000
    hours = dist_km / speed_kmh
    return dist_km, hours

# ======================
# Streamlit UI
# ======================
st.title("🌍 Flight Path Optimizer")
st.write("Plan great-circle routes between airports with support for multiple legs and speeds up to Mach 10 🚀")

# Multi-leg input
legs = st.number_input("How many flight legs?", min_value=1, max_value=5, value=1, step=1)

# Store results in session state
if "routes" not in st.session_state:
    st.session_state.routes = None

with st.form("route_form"):
    origin_airports = []
    dest_airports = []

    for i in range(legs):
        origin = st.selectbox(
            f"Leg {i+1} - Origin Airport",
            df_airports["display_name"].tolist(),
            key=f"origin_{i}"
        )
        dest = st.selectbox(
            f"Leg {i+1} - Destination Airport",
            df_airports["display_name"].tolist(),
            key=f"dest_{i}"
        )
        origin_airports.append(origin)
        dest_airports.append(dest)

    # Speed selector (up to Mach 10)
    mach_speed = 1225  # km/h at sea level approx
    speed_choice = st.slider("Cruise Speed (km/h)", min_value=200, max_value=mach_speed*10, value=900, step=50)

    submitted = st.form_submit_button("✈️ Compute Route")

if submitted:
    routes = []
    total_dist = 0
    total_time = 0

    for i in range(legs):
        o = df_airports[df_airports["display_name"] == origin_airports[i]].iloc[0]
        d = df_airports[df_airports["display_name"] == dest_airports[i]].iloc[0]

        dist, hrs = compute_distance_hours(o["latitude_deg"], o["longitude_deg"], d["latitude_deg"], d["longitude_deg"], speed_choice)
        path = great_circle_points(o["latitude_deg"], o["longitude_deg"], d["latitude_deg"], d["longitude_deg"], n_points=200)

        routes.append((o, d, path, dist, hrs))
        total_dist += dist
        total_time += hrs

    # Save to session state
    st.session_state.routes = (routes, total_dist, total_time)

# ======================
# Display results
# ======================
if st.session_state.routes:
    routes, total_dist, total_time = st.session_state.routes

    st.success(f"✅ Total Distance: {total_dist:.2f} km | Estimated Time: {total_time:.2f} hours")

    # Create map
    m = folium.Map(location=[20, 0], zoom_start=2)

    for o, d, path, dist, hrs in routes:
        folium.Marker([o["latitude_deg"], o["longitude_deg"]], popup=f"{o['display_name']}").add_to(m)
        folium.Marker([d["latitude_deg"], d["longitude_deg"]], popup=f"{d['display_name']}").add_to(m)
        folium.PolyLine(path, color="blue", weight=2.5, opacity=1).add_to(m)

    st_folium(m, width=800, height=500)
