import streamlit as st
import pandas as pd
import folium
from pyproj import Geod
from streamlit_folium import st_folium

# ----------------------------
# Load airport data
# ----------------------------
@st.cache_data
def load_airports():
    df = pd.read_csv("data/airports.csv", low_memory=False)

    # Normalize column names
    if "iata" in df.columns:
        df.rename(columns={"iata": "iata_code"}, inplace=True)

    # Keep only valid IATA codes
    df = df[df["iata_code"].notna() & (df["iata_code"] != "\\N")]

    # Drop duplicates
    df = df.drop_duplicates(subset=["iata_code"])

    return df

# ----------------------------
# Great-circle calculator
# ----------------------------
def great_circle_points(lat1, lon1, lat2, lon2, n_points=200):
    geod = Geod(ellps="WGS84")
    line = geod.npts(lon1, lat1, lon2, lat2, n_points)
    lons, lats = zip(*([(lon1, lat1)] + line + [(lon2, lat2)]))
    return lats, lons

# ----------------------------
# Streamlit App
# ----------------------------
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")

st.title("✈️ Flight Path Optimizer")
st.markdown("Find great-circle routes between airports worldwide 🌍")

df_airports = load_airports()

# Build display labels
df_airports["label"] = (
    df_airports["municipality"].fillna("Unknown City") + " – " +
    df_airports["name"].fillna("Unknown Airport") + " (" +
    df_airports["iata_code"] + ")"
)

# Sort alphabetically
df_airports = df_airports.sort_values("label")

# Dropdowns
st.sidebar.header("Select Route")
origin_label = st.sidebar.selectbox("Origin Airport", df_airports["label"])
dest_label = st.sidebar.selectbox("Destination Airport", df_airports["label"])

# Speed input (up to Mach 10 ≈ 12,348 km/h)
speed = st.sidebar.number_input("Cruise Speed (km/h)", min_value=300, max_value=12348, value=900, step=50)

# Multi-leg option
multi_leg = st.sidebar.checkbox("Add intermediate stop(s)?")
stops = []
if multi_leg:
    num_stops = st.sidebar.number_input("Number of stops", min_value=1, max_value=5, value=1, step=1)
    for i in range(num_stops):
        stop_label = st.sidebar.selectbox(f"Stop {i+1}", df_airports["label"], key=f"stop_{i}")
        stops.append(stop_label)

# Compute button
if st.sidebar.button("Compute Route"):
    # Look up origin/destination
    origin = df_airports[df_airports["label"] == origin_label].iloc[0]
    dest = df_airports[df_airports["label"] == dest_label].iloc[0]

    # Route legs
    route_labels = [origin_label] + stops + [dest_label]
    route_points = [origin] + [df_airports[df_airports["label"] == s].iloc[0] for s in stops] + [dest]

    # Initialize map centered on origin
    m = folium.Map(location=[origin["latitude_deg"], origin["longitude_deg"]], zoom_start=3)

    total_distance = 0.0

    # Draw each leg
    for i in range(len(route_points) - 1):
        o, d = route_points[i], route_points[i+1]
        lats, lons = great_circle_points(
            o["latitude_deg"], o["longitude_deg"],
            d["latitude_deg"], d["longitude_deg"], n_points=200
        )
        folium.PolyLine(list(zip(lats, lons)), color="blue", weight=3).add_to(m)
        folium.Marker([o["latitude_deg"], o["longitude_deg"]], tooltip=route_labels[i]).add_to(m)
        total_distance += Geod(ellps="WGS84").inv(
            o["longitude_deg"], o["latitude_deg"],
            d["longitude_deg"], d["latitude_deg"]
        )[2] / 1000.0  # meters → km

    # Add destination marker
    folium.Marker([dest["latitude_deg"], dest["longitude_deg"]],
                  tooltip=route_labels[-1], icon=folium.Icon(color="red")).add_to(m)

    # Show map
    st_folium(m, width=1000, height=600)

    # Show stats
    st.subheader("📊 Route Stats")
    st.write(f"**Total Distance:** {total_distance:.1f} km")
    eta = total_distance / speed
    st.write(f"**ETA (@{speed} km/h):** {eta:.2f} hours")

