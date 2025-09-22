import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from geopy.distance import geodesic

# --- Load airports dataset ---
@st.cache_data
def load_airports():
    df = pd.read_csv("data/airports.csv")
    # Keep only rows with valid IATA codes
    df = df[df['iata'].notna() & (df['iata'] != '\\N')]
    return df[["iata", "name", "city", "country", "lat", "lon"]]

df_airports = load_airports()

# Sort airport codes alphabetically
airport_codes = sorted(df_airports["iata"].unique())

# --- App Title ---
st.set_page_config(page_title="Flight Path Optimizer", layout="wide")
st.title("✈️ Flight Path Optimizer")

# --- Sidebar for inputs ---
st.sidebar.header("🛫 Route Settings")

origin = st.sidebar.selectbox(
    "Select Origin Airport",
    options=airport_codes,
    index=airport_codes.index("CCU") if "CCU" in airport_codes else 0,
)

destination = st.sidebar.selectbox(
    "Select Destination Airport",
    options=airport_codes,
    index=airport_codes.index("BOM") if "BOM" in airport_codes else 1,
)

cruise_speed = st.sidebar.number_input(
    "Cruise Speed (km/h)", min_value=400, max_value=1000, value=900
)

# --- Main section ---
if st.sidebar.button("Compute Route"):
    # Lookup airports
    origin_row = df_airports[df_airports["iata"] == origin].iloc[0]
    dest_row = df_airports[df_airports["iata"] == destination].iloc[0]

    # Compute distance and ETA
    distance_km = geodesic(
        (origin_row["lat"], origin_row["lon"]),
        (dest_row["lat"], dest_row["lon"])
    ).km
    eta_hours = distance_km / cruise_speed

    # --- Show results ---
    st.subheader("📊 Route Information")
    st.success(f"**From:** {origin} ({origin_row['city']}, {origin_row['country']})")
    st.success(f"**To:** {destination} ({dest_row['city']}, {dest_row['country']})")
    st.info(f"**Distance:** {distance_km:.1f} km")
    st.info(f"**Estimated Time (@{cruise_speed} km/h):** {eta_hours:.2f} hours")

    # --- Map visualization ---
    m = folium.Map(
        location=[(origin_row["lat"] + dest_row["lat"]) / 2,
                  (origin_row["lon"] + dest_row["lon"]) / 2],
        zoom_start=5
    )

    folium.Marker(
        [origin_row["lat"], origin_row["lon"]],
        tooltip=f"Origin: {origin} - {origin_row['city']}",
        icon=folium.Icon(color="green", icon="plane", prefix="fa")
    ).add_to(m)

    folium.Marker(
        [dest_row["lat"], dest_row["lon"]],
        tooltip=f"Destination: {destination} - {dest_row['city']}",
        icon=folium.Icon(color="red", icon="flag", prefix="fa")
    ).add_to(m)

    folium.PolyLine(
        [(origin_row["lat"], origin_row["lon"]),
         (dest_row["lat"], dest_row["lon"])],
        color="blue", weight=3
    ).add_to(m)

    st_folium(m, width=900, height=550)
else:
    st.info("👆 Select airports and click **Compute Route** to see the map.")
