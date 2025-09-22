import pandas as pd
from geopy.distance import great_circle
import folium
from pathlib import Path

# Path to airports dataset
AIRPORTS_CSV = Path("data/airports.csv")

def load_airports():
    """Load airports dataset into a pandas DataFrame."""
    df = pd.read_csv(AIRPORTS_CSV)
    # Keep only useful columns
    df = df[["id", "ident", "name", "iso_country", "municipality", "latitude_deg", "longitude_deg"]]
    return df

def find_airport(df, code):
    """Find airport by ICAO (ident) or IATA code."""
    airport = df[df["ident"] == code.upper()]
    if airport.empty:
        raise ValueError(f"Airport code '{code}' not found!")
    return airport.iloc[0]

def plot_route(origin, destination):
    """Plot a great-circle route between two airports."""
    coords = [
        (origin["latitude_deg"], origin["longitude_deg"]),
        (destination["latitude_deg"], destination["longitude_deg"])
    ]

    # Initialize folium map centered halfway
    midpoint = (
        (coords[0][0] + coords[1][0]) / 2,
        (coords[0][1] + coords[1][1]) / 2,
    )
    m = folium.Map(location=midpoint, zoom_start=3)

    # Add markers
    folium.Marker(coords[0], popup=f"Origin: {origin['name']}").add_to(m)
    folium.Marker(coords[1], popup=f"Destination: {destination['name']}").add_to(m)

    # Draw route line
    folium.PolyLine(coords, color="blue", weight=2.5).add_to(m)

    # Save map to file
    out_file = Path("route_map.html")
    m.save(out_file)
    print(f"✅ Route map saved as {out_file.absolute()}")

def main():
    df = load_airports()

    # Example: From JFK (New York) to LHR (London Heathrow)
    origin_code = input("Enter origin airport ICAO code (e.g., KJFK): ")
    dest_code = input("Enter destination airport ICAO code (e.g., EGLL): ")

    origin = find_airport(df, origin_code)
    dest = find_airport(df, dest_code)

    distance = great_circle(
        (origin["latitude_deg"], origin["longitude_deg"]),
        (dest["latitude_deg"], dest["longitude_deg"])
    ).kilometers

    print(f"Great-circle distance from {origin['name']} to {dest['name']}: {distance:.2f} km")

    plot_route(origin, dest)

if __name__ == "__main__":
    main()
