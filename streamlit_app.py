import streamlit as st
import pandas as pd
import folium
from pathlib import Path
from streamlit_folium import st_folium


# -------------------------------
# Load airport dataset
# -------------------------------
@st.cache_data
def load_airports():
    csv_path = Path("data/airports.csv")
    df = pd.read_csv(csv_path, low_memory=False)

    # Normalize column names
    df.columns = df.columns.str.lower()

    # Detect which column contains IATA codes
    if "iata" in df.columns:
        code_col = "iata"
    elif "iata_code" in df.columns:
        code_col = "iata_code"
    elif "ident" in df.columns:  # fallback
        code_col = "ident"
    else:
        st.error("❌ Could not find an IATA column in airports.csv")
        st.stop()

    # Keep only valid codes
    df = df[df[code_col].notna() & (df[code_col] != "\\N")]

    # Standardize column names
    df = df.rename(columns={code_col: "iata"})

    return df[["iata", "name", "latitude_deg", "longitude_deg"]]


# -------------------------------
# Compute distance (Haversine)
# -------------------------------
from math import radians, cos, sin, asin, sqrt

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


# -------------------------------
# Main Streamlit app
# -------------------------------
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")

st.title("✈️ Flight Path Optimizer")
st.markdown("Compute routes and visualize flight paths between airports.")

# Load dataset
df_airports = load_airports()
airport_codes = sorted(df_airports["iata"].unique())

# UI - airport selection
col1, col2 = st.columns(2)
with col1:
    origin = st.selectbox("Select Origin Airport", airport_codes, index=airport_codes.index("CCU") if "CCU" in airport_codes else 0)
with col2:
    dest = st.selectbox("Select Destination Airport", airport_codes, index=airport_codes.index("BOM") if "BOM" in airport_codes else 1)

# Cruise speed
cruise_speed = st.slider("Cruise Speed (km/h)", 500, 950, 850)

# Compute button
if st.button("Compute Route"):
    if origin == dest:
        st.warning("⚠️ Origin and destination cannot be the same.")
    else:
        o = df_airports[df_airports["iata"] == origin].iloc[0]
        d = df_airports[df_airports["iata"] == dest].iloc[0]

        dist_km = haversine(o["latitude_deg"], o["longitude_deg"], d["latitude_deg"], d["longitude_deg"])
        eta_hr = dist_km / cruise_speed

        st.success(f"**Distance:** {dist_km:.1f} km | **ETA:** {eta_hr:.2f} hours")

        # Create map
        m = folium.Map(location=[(o["latitude_deg"] + d["latitude_deg"]) / 2,
                                 (o["longitude_deg"] + d["longitude_deg"]) / 2],
                       zoom_start=4, tiles="CartoDB positron")

        # Add markers
        folium.Marker([o["latitude_deg"], o["longitude_deg"]],
                      popup=f"{o['iata']} - {o['name']}", tooltip=origin,
                      icon=folium.Icon(color="blue")).add_to(m)
        folium.Marker([d["latitude_deg"], d["longitude_deg"]],
                      popup=f"{d['iata']} - {d['name']}", tooltip=dest,
                      icon=folium.Icon(color="red")).add_to(m)

        # Draw route
        folium.PolyLine([(o["latitude_deg"], o["longitude_deg"]),
                         (d["latitude_deg"], d["longitude_deg"])],
                        color="darkblue", weight=3).add_to(m)

        # Render map
        st_folium(m, width=1000, height=600)
