# data/get_airports.py
import requests
from pathlib import Path

# URL for the OurAirports dataset (free, public)
URL = "https://ourairports.com/data/airports.csv"
OUT = Path(__file__).parent / "airports.csv"

def download():
    print("Downloading airports dataset...")
    r = requests.get(URL, stream=True)
    r.raise_for_status()
    with open(OUT, "wb") as f:
        for chunk in r.iter_content(1024 * 8):
            f.write(chunk)
    print(f"✅ Saved dataset to {OUT}")

if __name__ == "__main__":
    download()
