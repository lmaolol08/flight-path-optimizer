# main.py (updated)
import argparse
from pathlib import Path
from typing import List, Tuple
import math

import pandas as pd
import folium

from flight_utils import great_circle_points, haversine_km, bearing_between
from wind_fetcher import get_current_wind, tailwind_component_kmh

AIRPORTS_CSV = Path("data/airports.csv")

def load_airports():
    df = pd.read_csv(AIRPORTS_CSV, low_memory=False)
    # Normalize common column names
    # OurAirports has 'ident' for ICAO, 'iata_code' for IATA, and lat/lon fields like 'latitude_deg'
    # keep whole DF to be robust
    return df

def find_airport(df, code: str):
    code_up = str(code).upper().strip()
    if "ident" in df.columns:
        r = df[df["ident"].fillna("").str.upper() == code_up]
        if not r.empty:
            return r.iloc[0]
    # try iata_code
    for col in ["iata_code", "iata", "icao_code", "gps_code"]:
        if col in df.columns:
            r = df[df[col].fillna("").str.upper() == code_up]
            if not r.empty:
                return r.iloc[0]
    # last resort: search in name/municipality
    if "name" in df.columns:
        r = df[df["name"].fillna("").str.upper().str.contains(code_up, na=False)]
        if not r.empty:
            return r.iloc[0]
    raise ValueError(f"Airport '{code}' not found in {AIRPORTS_CSV}")

def compute_naive_time_hours(distance_km: float, cruise_kmh: float) -> float:
    return distance_km / cruise_kmh

def compute_wind_adjusted_time_hours(points: List[Tuple[float,float]],
                                     cruise_kmh: float,
                                     sample_rate: int = 8,
                                     verify_ssl: bool = True) -> float:
    """
    points: sequence of lat/lon along the route (n_points+1)
    sample_rate: how frequently to call wind API (1 => every segment; higher => fewer calls)
    returns total time in hours computed as sum over segments: d / (cruise_kmh + tailwind_kmh_at_segment)
    """
    total_hours = 0.0
    wind_cache = {}
    for i in range(len(points)-1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i+1]
        seg_km = haversine_km(lat1, lon1, lat2, lon2)
        bearing = bearing_between(lat1, lon1, lat2, lon2)
        # midpoint for wind sampling
        mid_lat = (lat1 + lat2) / 2.0
        mid_lon = (lon1 + lon2) / 2.0
        key = (round(mid_lat, 4), round(mid_lon, 4))
        tail_kmh = 0.0
        if (i % sample_rate) == 0:
            # attempt API call
            try:
                w = get_current_wind(mid_lat, mid_lon, verify_ssl=verify_ssl)
                wind_cache[key] = w
            except Exception as e:
                # API failed -> fallback to zero wind for this point
                wind_cache[key] = {"windspeed_kmh": 0.0, "winddirection_deg": 0.0}
        # use cached or default
        w = wind_cache.get(key, {"windspeed_kmh": 0.0, "winddirection_deg": 0.0})
        tail_kmh = tailwind_component_kmh(w["windspeed_kmh"], w["winddirection_deg"], bearing)
        # avoid crazy negative/zero ground speeds
        ground_speed = max(40.0, cruise_kmh + tail_kmh)
        seg_hours = seg_km / ground_speed
        total_hours += seg_hours
    return total_hours

def render_map(origin, dest, points, naive_hours, wind_hours=None, out="route_map.html"):
    mid_lat = sum(p[0] for p in points) / len(points)
    mid_lon = sum(p[1] for p in points) / len(points)
    m = folium.Map(location=(mid_lat, mid_lon), zoom_start=4, tiles="OpenStreetMap")

    folium.Marker(
        [origin["latitude_deg"], origin["longitude_deg"]],
        popup=f"{origin.get('ident','')}: {origin.get('name','')}",
        tooltip="Origin"
    ).add_to(m)

    folium.Marker(
        [dest["latitude_deg"], dest["longitude_deg"]],
        popup=f"{dest.get('ident','')}: {dest.get('name','')}",
        tooltip="Destination"
    ).add_to(m)

    folium.PolyLine(points, weight=3, opacity=0.8, popup="Great-circle route").add_to(m)

    # add summary box
    html = f"<div style='background:white;padding:8px;border-radius:6px;'><b>Distance:</b> {sum(haversine_km(points[i][0],points[i][1],points[i+1][0],points[i+1][1]) for i in range(len(points)-1)):.1f} km<br>"
    html += f"<b>Naive ETA:</b> {naive_hours*60:.0f} minutes ({naive_hours:.2f} h)<br>"
    if wind_hours is not None:
        html += f"<b>Wind-adjusted ETA:</b> {wind_hours*60:.0f} minutes ({wind_hours:.2f} h)<br>"
        html += f"<b>Difference:</b> {(wind_hours-naive_hours)*60:.0f} min</div>"
    else:
        html += "</div>"

    folium.map.Marker(
        (mid_lat, mid_lon),
        icon=folium.DivIcon(html=html)
    ).add_to(m)

    out_path = Path(out)
    m.save(out_path)
    print(f"Saved map to {out_path.absolute()}")

def main():
    parser = argparse.ArgumentParser(description="Flight Path Optimizer - medium MVP (time estimate + optional wind)")
    parser.add_argument("--from", dest="origin", required=True)
    parser.add_argument("--to", dest="dest", required=True)
    parser.add_argument("--points", type=int, default=200)
    parser.add_argument("--cruise", type=float, default=900.0, help="Cruise speed (km/h) default 900")
    parser.add_argument("--use-wind", action="store_true", help="Fetch wind data and compute wind-adjusted ETA")
    parser.add_argument("--sample-rate", type=int, default=8, help="Sample wind every N segments (default 8)")
    parser.add_argument("--out", default="route_map.html")
    parser.add_argument("--no-ssl-verify", action="store_true", help="If SSL certs fail, disable verification (not for prod)")
    args = parser.parse_args()

    df = load_airports()
    origin = find_airport(df, args.origin)
    dest = find_airport(df, args.dest)

    lat1, lon1 = float(origin["latitude_deg"]), float(origin["longitude_deg"])
    lat2, lon2 = float(dest["latitude_deg"]), float(dest["longitude_deg"])

    points = great_circle_points(lat1, lon1, lat2, lon2, n_points=args.points)
    distance_km = sum(haversine_km(points[i][0], points[i][1], points[i+1][0], points[i+1][1]) for i in range(len(points)-1))
    naive_hours = compute_naive_time_hours(distance_km, args.cruise)

    wind_hours = None
    if args.use_wind:
        print("Fetching wind data (may take a moment depending on sample rate)...")
        wind_hours = compute_wind_adjusted_time_hours(points, args.cruise, sample_rate=args.sample_rate, verify_ssl=not args.no_ssl_verify)

    print(f"Distance: {distance_km:.1f} km")
    print(f"Naive ETA (@{args.cruise:.0f} km/h): {naive_hours*60:.0f} min ({naive_hours:.2f} h)")
    if wind_hours is not None:
        delta_min = (wind_hours - naive_hours) * 60.0
        print(f"Wind-adjusted ETA: {wind_hours*60:.0f} min ({wind_hours:.2f} h)  (difference {delta_min:.0f} min)")

    render_map(origin, dest, points, naive_hours, wind_hours, out=args.out)
    print("Done.")

if __name__ == "__main__":
    main()
