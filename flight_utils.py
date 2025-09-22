# flight_utils.py
import math
from typing import List, Tuple

R_EARTH_KM = 6371.0088

def deg2rad(d: float) -> float:
    return d * math.pi / 180.0

def rad2deg(r: float) -> float:
    return r * 180.0 / math.pi

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    φ1, φ2 = deg2rad(lat1), deg2rad(lat2)
    dφ = deg2rad(lat2 - lat1)
    dλ = deg2rad(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R_EARTH_KM * c

def bearing_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    φ1, φ2 = deg2rad(lat1), deg2rad(lat2)
    λ1, λ2 = deg2rad(lon1), deg2rad(lon2)
    y = math.sin(λ2 - λ1) * math.cos(φ2)
    x = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(λ2 - λ1)
    θ = math.atan2(y, x)
    return (rad2deg(θ) + 360.0) % 360.0

def destination_point(lat: float, lon: float, bearing_deg: float, distance_km: float) -> Tuple[float, float]:
    # returns (lat2, lon2)
    δ = distance_km / R_EARTH_KM
    φ1 = deg2rad(lat); λ1 = deg2rad(lon); θ = deg2rad(bearing_deg)
    φ2 = math.asin(math.sin(φ1)*math.cos(δ) + math.cos(φ1)*math.sin(δ)*math.cos(θ))
    λ2 = λ1 + math.atan2(math.sin(θ)*math.sin(δ)*math.cos(φ1), math.cos(δ) - math.sin(φ1)*math.sin(φ2))
    lat2 = rad2deg(φ2)
    lon2 = rad2deg(λ2)
    # normalize lon to [-180, 180]
    lon2 = ((lon2 + 180) % 360) - 180
    return lat2, lon2

def great_circle_points(lat1: float, lon1: float, lat2: float, lon2: float, n_points: int = 100) -> List[Tuple[float,float]]:
    φ1, λ1 = deg2rad(lat1), deg2rad(lon1)
    φ2, λ2 = deg2rad(lat2), deg2rad(lon2)
    sin_dφ = math.sin((φ2 - φ1)/2.0)
    sin_dλ = math.sin((λ2 - λ1)/2.0)
    a = sin_dφ**2 + math.cos(φ1)*math.cos(φ2)*sin_dλ**2
    δ = 2 * math.asin(min(1, math.sqrt(a)))
    if δ == 0:
        return [(lat1, lon1) for _ in range(n_points+1)]
    pts = []
    for i in range(n_points+1):
        f = i / n_points
        A = math.sin((1 - f) * δ) / math.sin(δ)
        B = math.sin(f * δ) / math.sin(δ)
        x = A*math.cos(φ1)*math.cos(λ1) + B*math.cos(φ2)*math.cos(λ2)
        y = A*math.cos(φ1)*math.sin(λ1) + B*math.cos(φ2)*math.sin(λ2)
        z = A*math.sin(φ1) + B*math.sin(φ2)
        φi = math.atan2(z, math.sqrt(x*x + y*y))
        λi = math.atan2(y, x)
        pts.append((rad2deg(φi), rad2deg(λi)))
    return pts
