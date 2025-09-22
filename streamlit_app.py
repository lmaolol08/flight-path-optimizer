import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from pyproj import Geod

# ----------------------------
# Load airports dataset
# ----------------------------
@st.cache_data
def load_airports():
    df = pd.read_csv("data/airports.csv", low_memory=False)
    df = df[df['iata'].notna() & (df['iata'] != '\\N')]
    df = df[['iata', 'name', 'municipality', 'latitude_deg', 'longitude_deg']].drop_duplicates()
    return df

df_airports = load_airports()
iata_codes = sorted(df_airports['iata'].unique())
cities = sorted(df_airports['municipality'].dropna().unique())

geod = Geod(ellps="WGS84")

# ----------------------------
# Helper functions
# ----------------------------
def great_circle_points(lat1, lon1, lat2, lon2, n_points=200):
    lons, lats = geod.npts(lon1, lat1, lon2, lat2, n_points)
    return [(lat1, lon1)] + [(lat, lon) for lon, lat in zip(lons, lats)] + [(lat2, lon2)]

def compute_distance(lat1, lon1, lat2, lon2):
    az12, az21, dist = geod.inv(lon1, lat1, lon2, lat2)
    return dist / 1000.0  # km

def airport_lookup_by_city(city_query):
    """Return airports for a city query (autocomplete style)."""
    matches = df_airports[df_airports["municipality"].str.contains(city_query, case=False, na=False)]
    return matches

def airport_lookup_by_code(code_query):
    """Return airports for an IATA code query (autocomplete style)."""
    matches = df_airports[df_airports["iata"].str.contains(code_query.upper(), na=False)]
    return matches

# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")

st.title("✈️ Flight Path Optimizer")

st.sidebar.header("Flight Settings")

# Select input mode
mode = st.sidebar.radio("Choose Input Mode:", ["By Airport Code", "By City Name"])

legs = []
num_legs = st.sidebar.number_input("Number of legs", 1, 5, 1)

for i in range(num_legs + 1):
    if mode == "By Airport Code":
        # Autocomplete airport code
        code_query = st.sidebar.text_input(f"Enter IATA code (Airport {i+1})", key=f"code_query_{i}")
        if code_query:
            matches = airport_lookup_by_code(code_query)
            if not matches.empty:
                leg_airport = st.sidebar.selectbox(
                    f"Matching airports for {code_query}",
                    options=matches['iata'] + " - " + matches['municipality'] + " (" + matches['name'] + ")",
                    key=f"airport_code_{i}"
                )
                leg_code = leg_airport.split(" - ")[0]
            else:
                st.sidebar.warning("No matches found.")
                leg_code = None
        else:
            leg_code = None

    else:
        # Autocomplete city name
        city_query = st.sidebar.text_input(f"Enter City (Airport {i+1})", key=f"city_query_{i}")
        if city_query:
            matches = airport_lookup_by_city(city_query)
            if not matches.empty:
                leg_airport = st.sidebar.selectbox(
                    f"Airports in {city_query}",
                    options=matches['iata'] + " - " + matches['municipality'] + " (" + matches['name'] + ")",
                    key=f"airport_city_{i}"
                )
                leg_code = leg_airport.split(" - ")[0]
            else:
                st.sidebar.warning("No airports found for this city.")
                leg_code = None
        else:
            leg_code = None

    if leg_code:
        legs.append(leg_code)

speed = st.sidebar.slider("Cruise Speed (Mach)", 0.5, 10.0, 0.85, 0.05)
kmh_speed = speed * 1235.0  # Mach 1 = ~1235 km/h

# ----------------------------
# Route computation
# ----------------------------
if st.sidebar.button("Compute Route") and len(legs) > 1:
    total_distance = 0
    total_time = 0
    results = []

    # Initialize map centered on first airport
    origin = df_airports[df_airports["iata"] == legs[0]].iloc[0]
    m = folium.Map(location=[origin["latitude_deg"], origin["longitude_deg"]], zoom_start=3)

    for i in range(len(legs) - 1):
        o = df_airports[df_airports["iata"] == legs[i]].iloc[0]
        d = df_airports[df_airports["iata"] == legs[i + 1]].iloc[0]

        # Compute distance and ETA
        dist = compute_distance(o["latitude_deg"], o["longitude_deg"],
                                d["latitude_deg"], d["longitude_deg"])
        eta = dist / kmh_speed

        total_distance += dist
        total_time += eta
        results.append({
            "From": f"{o['iata']} ({o['municipality']})",
            "To": f"{d['iata']} ({d['municipality']})",
            "Distance (km)": round(dist, 1),
            "ETA (hours)": round(eta, 2)
        })

        # Plot great circle path
        path = great_circle_points(o["latitude_deg"], o["longitude_deg"],
                                   d["latitude_deg"], d["longitude_deg"], n_points=200)
        folium.PolyLine(path, color="blue", weight=2.5).add_to(m)

        # Add markers with IATA + City + Airport Name
        folium.Marker(
            [o["latitude_deg"], o["longitude_deg"]],
            popup=f"{o['iata']} - {o['municipality']}<br>{o['name']}"
        ).add_to(m)
        folium.Marker(
            [d["latitude_deg"], d["longitude_deg"]],
            popup=f"{d['iata']} - {d['municipality']}<br>{d['name']}"
        ).add_to(m)

    # --- Results Section ---
    st.subheader("📊 Leg-by-Leg Breakdown")
    st.dataframe(pd.DataFrame(results), use_container_width=True)

    st.subheader("🗺️ Route Map")
    st_folium(m, width=1000, height=600)
