import streamlit as st
import pandas as pd
import folium
from pathlib import Path
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt
from pyproj import Geod


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
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


# -------------------------------
# Generate Great Circle Path
# -------------------------------
def great_circle_points(lat1, lon1, lat2, lon2, n_points=100):
    geod = Geod(ellps="WGS84")
    lons, lats = geod.npts(lon1, lat1, lon2, lat2, n_points)
    # Include start + end
    lats = [lat1] + [lat for lat in lats] + [lat2]
    lons = [lon1] + [lon for lon in lons] + [lon2]
    return list(zip(lats, lons))


# -------------------------------
# Main Streamlit app
# -------------------------------
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")

st.title("✈️ Flight Path Optimizer")
st.markdown("Compute single or multi-leg flight routes between airports.")

# Load dataset
df_airports = load_airports()
airport_codes = sorted(df_airports["iata"].unique())

# -------------------------------
# Route Selection
# -------------------------------
st.subheader("🛫 Route Planner")

origin = st.selectbox("Select Origin Airport", airport_codes, index=airport_codes.index("CCU") if "CCU" in airport_codes else 0)
destination = st.selectbox("Select Destination Airport", airport_codes, index=airport_codes.index("BOM") if "BOM" in airport_codes else 1)

st.markdown("### ➕ Add Stopovers (optional)")
stops = st.multiselect("Choose intermediate airports", airport_codes)

# Cruise speed
st.markdown("### ⚡ Cruise Speed")
cruise_speed = st.slider("Set Speed (km/h)", 500, int(12348), 850)

# -------------------------------
# Session state management
# -------------------------------
if "route_computed" not in st.session_state:
    st.session_state.route_computed = False

colA, colB = st.columns([1,1])
with colA:
    if st.button("Compute Route"):
        st.session_state.route_computed = True
with colB:
    if st.button("Reset Route"):
        st.session_state.route_computed = False

# -------------------------------
# Show results if route computed
# -------------------------------
if st.session_state.route_computed:
    route = [origin] + stops + [destination]

    if len(route) != len(set(route)):
        st.warning("⚠️ Route contains duplicate airports. Please choose unique airports.")
        st.session_state.route_computed = False
    else:
        total_dist = 0
        total_time = 0
        legs_data = []

        # Center map on first airport
        o = df_airports[df_airports["iata"] == origin].iloc[0]
        m = folium.Map(location=[o["latitude_deg"], o["longitude_deg"]],
                       zoom_start=3, tiles="CartoDB positron")

        # Plot each leg
        for i in range(len(route) - 1):
            o = df_airports[df_airports["iata"] == route[i]].iloc[0]
            d = df_airports[df_airports["iata"] == route[i+1]].iloc[0]

            dist_km = haversine(o["latitude_deg"], o["longitude_deg"],
                                d["latitude_deg"], d["longitude_deg"])
            eta_hr = dist_km / cruise_speed
            total_dist += dist_km
            total_time += eta_hr

            # Collect leg data for table
            legs_data.append({
                "From": route[i],
                "To": route[i+1],
                "Distance (km)": f"{dist_km:.1f}",
                "ETA (hours)": f"{eta_hr:.2f}"
            })

            # Add markers
            folium.Marker([o["latitude_deg"], o["longitude_deg"]],
                          popup=f"{o['iata']} - {o['name']}", tooltip=route[i],
                          icon=folium.Icon(color="blue")).add_to(m)
            folium.Marker([d["latitude_deg"], d["longitude_deg"]],
                          popup=f"{d['iata']} - {d['name']}", tooltip=route[i+1],
                          icon=folium.Icon(color="red")).add_to(m)

            # Draw Great Circle Route
            path = great_circle_points(o["latitude_deg"], o["longitude_deg"],
                                       d["latitude_deg"], d["longitude_deg"], n_points=200)
            folium.PolyLine(path, color="darkblue", weight=3).add_to(m)

        # Results summary
        st.success(f"**Total Distance:** {total_dist:.1f} km | **ETA:** {total_time:.2f} hours @ {cruise_speed} km/h")

        # Leg-by-leg breakdown
        st.subheader("📊 Leg-by-Leg Breakdown")
        st.dataframe(pd.DataFrame(legs_data), use_container_width=True)

        # Render map
        st_folium(m, width=1000, height=600)
