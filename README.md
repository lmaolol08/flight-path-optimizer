# ✈️ Flight Path Optimizer  

<p align="center">
  <img src="https://img.shields.io/badge/Streamlit-Deployed-brightgreen?logo=streamlit" />
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" />
  <img src="https://img.shields.io/badge/Folium-Maps-orange?logo=leaflet" />
  <img src="https://img.shields.io/badge/Status-Active-success" />
</p>

## 🌍 Overview  
The **Flight Path Optimizer** is an interactive web app that calculates **optimal flight paths** between airports worldwide.  
It supports:  
✅ Multi-leg flight planning  
✅ Cruise speeds up to **Mach 10 (12,348 km/h)**  
✅ Leg-by-leg distance & ETA breakdown  
✅ Beautiful interactive maps powered by **Folium**  

Deployed with **Streamlit Cloud**, accessible from any browser. 🚀  

---

## 🎥 Demo  
👉 [**Live App Here**](https://airnavoptimizer.streamlit.app/)  

<p align="center">
  <img src="docs/demo.gif" width="700" />
</p>

---

## ✨ Features  
- 🛫 **Multi-leg routes** – Add stopovers between origin and destination.  
- ⚡ **Supersonic mode** – Choose speeds from 500 km/h up to **Mach 10**.  
- 📊 **Breakdown table** – Distance + ETA for every leg of your journey.  
- 🗺️ **Interactive maps** – Great circle routes drawn dynamically.  
- 🌐 **IATA airport search** – Autocomplete dropdown with global codes.  

---

## 🛠️ Tech Stack  
- **[Python](https://www.python.org/)** – Core programming language  
- **[Streamlit](https://streamlit.io/)** – Web app framework  
- **[Folium](https://python-visualization.github.io/folium/)** – Map rendering  
- **[PyProj](https://pyproj4.github.io/pyproj/stable/)** – Great circle math  
- **[Pandas](https://pandas.pydata.org/)** – Data handling  

---

## 🚀 Run Locally  

Clone the repo:
```bash
git clone https://github.com/lmaolol08/flight-path-optimizer.git
cd flight-path-optimizer

Create a virtual environment:
python -m venv venv
source venv/bin/activate    # (Linux/Mac)
venv\Scripts\activate       # (Windows)

Install dependencies:
pip install -r requirements.txt

Run the app:
streamlit run streamlit_app.py

📂 Project Structure
flight-path-optimizer/
│
├── data/                 # Airports dataset
├── outputs/              # Generated maps (local runs)
├── streamlit_app.py      # Main Streamlit web app
├── requirements.txt      # Dependencies
└── README.md             # Project documentation




