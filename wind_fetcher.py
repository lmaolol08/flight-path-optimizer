# wind_fetcher.py
import requests
from typing import Dict
import math

def get_current_wind(lat: float, lon: float, verify_ssl: bool = True, timeout: int = 8) -> Dict:
    """
    Returns a dict: {'windspeed_kmh': float, 'winddirection_deg': float}
    Uses Open-Meteo current_weather endpoint and requests km/h units.
    If the call fails, this function raises an exception.
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat:.6f}&longitude={lon:.6f}&current_weather=true&windspeed_unit=kmh"
    resp = requests.get(url, timeout=timeout, verify=verify_ssl)
    resp.raise_for_status()
    data = resp.json()
    cw = data.get("current_weather")
    if not cw:
        raise ValueError("No current_weather in API response")
    return {"windspeed_kmh": float(cw["windspeed"]), "winddirection_deg": float(cw["winddirection"])}

def tailwind_component_kmh(windspeed_kmh: float, winddirection_from_deg: float, aircraft_bearing_deg: float) -> float:
    """
    winddirection_from_deg: meteorological wind direction (degrees FROM which the wind is blowing)
    aircraft_bearing_deg: direction aircraft is travelling (0..360, deg from north)
    returns tailwind component in km/h (positive tailwind, negative headwind)
    """
    # wind vector points TO = from + 180
    wind_to = (winddirection_from_deg + 180.0) % 360.0
    # smallest signed angle between wind_to and aircraft_bearing in [-180,180]
    diff = ((wind_to - aircraft_bearing_deg + 180.0) % 360.0) - 180.0
    # tailwind component:
    return windspeed_kmh * math.cos(math.radians(diff))
