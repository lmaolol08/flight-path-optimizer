# optimize.py
import argparse
from pathlib import Path
from typing import List, Tuple
import math

import networkx as nx
import folium
import pandas as pd

from flight_utils import great_circle_points, destination_point, haversine_km, bearing_between
from wind_fetcher import get_current_wind, tailwind_component_kmh

AIRPORTS_CSV = Path("data/airports.csv")

def load_airports():
    return pd.read_csv(AIRPORTS_CSV, low_memory=False)

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
    raise ValueError(f"Airport '{code}' not found")

def build_corridor_slices(lat1, lon1, lat2, lon2, slices=40, lateral_offsets_km=[-100, 0, 100]):
    # create 'slices' along great circle: sample points, then for each sample create lateral nodes offset perpendicular to path
    gc = great_circle_points(lat1, lon1, lat2, lon2, n_points=slices)
    slices_nodes = []
    for i in range(len(gc)-1):
        a = gc[i]
        b = gc[i+1]
        mid_lat = (a[0] + b[0]) / 2.0
        mid_lon = (a[1] + b[1]) / 2.0
        bearing = bearing_between(a[0], a[1], b[0], b[1])
        # perpendicular left is bearing-90, right is bearing+90
        nodes = []
        for offset in lateral_offsets_km:
            if offset == 0:
                nodes.append((mid_lat, mid_lon))
            else:
                perp_bearing = (bearing + 90.0) % 360.0 if offset > 0 else (bearing - 90.0) % 360.0
                lat_off, lon_off = destination_point(mid_lat, mid_lon, perp_bearing, abs(offset))
                nodes.append((lat_off, lon_off))
        slices_nodes.append(nodes)
    return slices_nodes

def build_graph(slices_nodes, cruise_kmh=900.0, use_wind=True, verify_ssl=True):
    G = nx.DiGraph()
    wind_cache = {}
    # add nodes
    for i, nodes in enumerate(slices_nodes):
        for j, (lat, lon) in enumerate(nodes):
            nid = (i, j)
            G.add_node(nid, lat=lat, lon=lon)
    # connect edges between slice i and i+1 (fully connected between two consecutive slices)
    for i in range(len(slices_nodes) - 1):
        for j, (lat1, lon1) in enumerate(slices_nodes[i]):
            for k, (lat2, lon2) in enumerate(slices_nodes[i+1]):
                d = haversine_km(lat1, lon1, lat2, lon2)
                bearing = bearing_between(lat1, lon1, lat2, lon2)
                mid_lat = (lat1 + lat2) / 2.0
                mid_lon = (lon1 + lon2) / 2.0
                key = (round(mid_lat,4), round(mid_lon,4))
                w = {"windspeed_kmh": 0.0, "winddirection_deg": 0.0}
                if use_wind:
                    try:
                        if key not in wind_cache:
                            wind_cache[key] = get_current_wind(mid_lat, mid_lon, verify_ssl=verify_ssl)
                        w = wind_cache[key]
                    except Exception:
                        w = {"windspeed_kmh": 0.0, "winddirection_deg": 0.0}
                tail = tailwind_component_kmh(w["windspeed_kmh"], w["winddirection_deg"], bearing)
                ground_speed = max(40.0, cruise_kmh + tail)
                travel_time_h = d / ground_speed
                G.add_edge((i,j), (i+1,k), weight=travel_time_h, distance_km=d)
    return G

def find_endpoints_nodes(slices_nodes):
    start_nodes = slices_nodes[0]
    end_nodes = slices_nodes[-1]
    # choose center node (index where offset==0) if present (we used offsets list like [-X,0,X])
    # center index is usually len(offsets)//2
    center_idx = len(start_nodes) // 2
    start_id = (0, center_idx)
    end_id = (len(slices_nodes)-1, center_idx)
    return start_id, end_id

def heuristic(u, v, G, cruise_kmh):
    # u and v are node ids; heuristic = great-circle distance / cruise speed (hours)
    lat_u, lon_u = G.nodes[u]['lat'], G.nodes[u]['lon']
    lat_v, lon_v = G.nodes[v]['lat'], G.nodes[v]['lon']
    d = haversine_km(lat_u, lon_u, lat_v, lon_v)
    return d / cruise_kmh

def extract_path_coords(path_nodes, G):
    coords = []
    for nid in path_nodes:
        coords.append((G.nodes[nid]['lat'], G.nodes[nid]['lon']))
    return coords

def run_optimization(origin_code, dest_code, slices=40, lateral_offsets_km=[-100,0,100], cruise_kmh=900.0, use_wind=True, verify_ssl=True, out="optimized_map.html"):
    df = load_airports()
    origin = find_airport(df, origin_code)
    dest = find_airport(df, dest_code)
    lat1, lon1 = float(origin["latitude_deg"]), float(origin["longitude_deg"])
    lat2, lon2 = float(dest["latitude_deg"]), float(dest["longitude_deg"])
    slices_nodes = build_corridor_slices(lat1, lon1, lat2, lon2, slices=slices, lateral_offsets_km=lateral_offsets_km)
    G = build_graph(slices_nodes, cruise_kmh=cruise_kmh, use_wind=use_wind, verify_ssl=verify_ssl)
    start, goal = find_endpoints_nodes(slices_nodes)
    # A* search
    try:
        path = nx.astar_path(G, start, goal, heuristic=lambda u,v: heuristic(u, goal, G, cruise_kmh), weight="weight")
    except Exception as e:
        raise RuntimeError(f"A* search failed: {e}")
    path_coords = extract_path_coords(path, G)
    # compute time sum and naive GC time
    total_opt_h = sum(G.edges[path[i], path[i+1]]['weight'] for i in range(len(path)-1))
    # naive great-circle for comparison
    gc_pts = great_circle_points(lat1,lon1,lat2,lon2,n_points=slices*2)
    gc_dist = sum(haversine_km(gc_pts[i][0],gc_pts[i][1],gc_pts[i+1][0],gc_pts[i+1][1]) for i in range(len(gc_pts)-1))
    naive_h = gc_dist / cruise_kmh

    # render map: both GC and optimized
    mid_lat = (lat1 + lat2) / 2.0
    mid_lon = (lon1 + lon2) / 2.0
    m = folium.Map(location=(mid_lat, mid_lon), zoom_start=4, tiles="OpenStreetMap")
    folium.PolyLine(gc_pts, weight=2, color="blue", popup="Great-circle").add_to(m)
    folium.PolyLine(path_coords, weight=3, color="green", popup="Optimized path").add_to(m)
    folium.Marker([lat1,lon1], popup=f"Origin: {origin.get('ident','')}").add_to(m)
    folium.Marker([lat2,lon2], popup=f"Destination: {dest.get('ident','')}").add_to(m)

    html = f"<div style='background:white;padding:8px;border-radius:6px;'><b>GC dist:</b> {gc_dist:.1f} km<br><b>Naive ETA:</b> {naive_h*60:.0f} min<br><b>Optimized ETA:</b> {total_opt_h*60:.0f} min<br><b>Delta:</b> {(total_opt_h-naive_h)*60:.0f} min</div>"
    folium.map.Marker(((mid_lat),(mid_lon)), icon=folium.DivIcon(html=html)).add_to(m)
    m.save(out)
    return {"gc_km": gc_dist, "naive_h": naive_h, "opt_h": total_opt_h, "map": Path(out).absolute()}

def main():
    parser = argparse.ArgumentParser(description="Optimize route through corridor using wind-adjusted time")
    parser.add_argument("--from", dest="origin", required=True)
    parser.add_argument("--to", dest="dest", required=True)
    parser.add_argument("--slices", type=int, default=40)
    parser.add_argument("--offsets", type=float, nargs="+", default=[-100, 0, 100], help="Lateral offsets in km (e.g. -100 0 100)")
    parser.add_argument("--cruise", type=float, default=900.0)
    parser.add_argument("--use-wind", action="store_true")
    parser.add_argument("--no-ssl-verify", action="store_true")
    parser.add_argument("--out", default="optimized_map.html")
    args = parser.parse_args()

    res = run_optimization(args.origin, args.dest, slices=args.slices, lateral_offsets_km=args.offsets, cruise_kmh=args.cruise, use_wind=args.use_wind, verify_ssl=not args.no_ssl_verify, out=args.out)
    print("Done. Results:")
    print(f"Great-circle distance: {res['gc_km']:.1f} km")
    print(f"Naive ETA: {res['naive_h']*60:.0f} min")
    print(f"Optimized ETA: {res['opt_h']*60:.0f} min")
    print(f"Saved map to {res['map']}")

if __name__ == "__main__":
    main()
