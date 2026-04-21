import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import hashlib
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# --- Page Configuration ---
st.set_page_config(
    page_title="Wildfire Risk Dashboard", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize External Services ---
geolocator = Nominatim(user_agent="wildfire_risk_app")

# --- Initialize Session State ---
if 'lat' not in st.session_state:
    st.session_state.lat = 19.0760 # Default to Mumbai
if 'lon' not in st.session_state:
    st.session_state.lon = 72.8777
if 'location_name' not in st.session_state:
    st.session_state.location_name = "Mumbai"
if 'prediction' not in st.session_state:
    st.session_state.prediction = None
if 'current_features' not in st.session_state:
    st.session_state.current_features = {
        "temperature": 32.0, "NDVI": 0.15, "humidity": 65.0, "wind_speed": 12.0, "slope": 5.0
    }

# --- Dynamic Environmental Data Function ---
def get_environmental_data(lat, lon, location_name):
    """Fetches real weather from Open-Meteo and simulates terrain based on location."""
    
    # 1. Fetch Real Weather Data (Open-Meteo is free, no API key needed)
    temp, humidity, wind_speed = 35.0, 40.0, 15.0 # Fallbacks
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("current", {})
            temp = data.get("temperature_2m", temp)
            humidity = data.get("relative_humidity_2m", humidity)
            wind_speed = data.get("wind_speed_10m", wind_speed)
    except Exception as e:
        pass # Silently fallback to default values if API fails

    # 2. Simulate Terrain & Satellite Data based on City Name
    loc_lower = str(location_name).lower()
    if "mumbai" in loc_lower:
        ndvi, slope = 0.15, 5.0    # Coastal/Urban
    elif "pune" in loc_lower:
        ndvi, slope = 0.35, 15.0   # Hilly/Deccan plateau
    elif "nagpur" in loc_lower:
        ndvi, slope = 0.40, 8.0    # Central plains/Forests
    else:
        # Generate stable pseudo-random terrain based on coordinates for unlisted places
        coord_str = f"{lat:.4f},{lon:.4f}"
        hash_val = int(hashlib.md5(coord_str.encode()).hexdigest(), 16)
        ndvi = 0.1 + (hash_val % 50) / 100.0  # Range: 0.1 to 0.59
        slope = float(hash_val % 45)          # Range: 0.0 to 44.0

    return {
        "temperature": round(temp, 1),
        "NDVI": round(ndvi, 2),
        "humidity": round(humidity, 1),
        "wind_speed": round(wind_speed, 1),
        "slope": round(slope, 1)
    }

# --- 1. Sidebar Layout & Text Search ---
with st.sidebar:
    st.title("🔥 Wildfire Prediction")
    st.markdown("---")
    
    st.write("**Location Selection**")
    st.caption("Type a city/country, or click anywhere on the map.")
    
    # Text-based location search
    search_query = st.text_input("Search Location", value=st.session_state.location_name)
    
    # If user types a new location, geocode it
    if search_query and search_query != st.session_state.location_name:
        try:
            location = geolocator.geocode(search_query)
            if location:
                st.session_state.lat = location.latitude
                st.session_state.lon = location.longitude
                st.session_state.location_name = search_query
                st.session_state.prediction = None 
                st.rerun() 
            else:
                st.error("Location not found. Please try another name.")
        except GeocoderTimedOut:
            st.warning("Geocoding service timed out. Try again.")

    st.markdown(f"**Current Coordinates:**\n\nLat: `{st.session_state.lat:.4f}` | Lon: `{st.session_state.lon:.4f}`")
    
    forecast = st.selectbox("Forecast Window", ["Next 24 Hours", "Next 48 Hours", "Next 7 Days"])
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("Generate Risk Map", type="primary", use_container_width=True)

# --- 2. Backend Integration & Feature Generation ---
if generate_btn:
    with st.spinner("Fetching live weather & computing risk..."):
        # Generate dynamic features for the specific location
        dynamic_features = get_environmental_data(
            st.session_state.lat, 
            st.session_state.lon, 
            st.session_state.location_name
        )
        # Save to session state so the UI updates
        st.session_state.current_features = dynamic_features
        
        # Send dynamic features to your FastAPI backend
        try:
            response = requests.post(
                "https://wildfire-protection.onrender.com/predict", 
                json=st.session_state.current_features, 
                timeout=10
            )
            if response.status_code == 200:
                st.session_state.prediction = response.json()
            else:
                st.sidebar.error(f"Backend Error: Status {response.status_code}")
        except requests.exceptions.RequestException:
            st.sidebar.error("Failed to connect. Ensure FastAPI is running.")

# --- Layout: Main Center & Right Panel ---
col_map, col_panel = st.columns([2.5, 1], gap="large")

# --- 3. Main Center: Map View & Click Handling ---
with col_map:
    st.subheader(f"Geospatial View: {st.session_state.location_name}")
    
    # Create Base Map
    m = folium.Map(
        location=[st.session_state.lat, st.session_state.lon], 
        zoom_start=10, 
        tiles="CartoDB dark_matter"
    )

    # Add Marker based on Prediction
    risk_cat = "Unknown"
    marker_color = "blue"
    if st.session_state.prediction:
        risk_cat = st.session_state.prediction.get("risk_category", "Low")
        color_mapping = {"Low": "green", "Medium": "orange", "High": "red"}
        marker_color = color_mapping.get(risk_cat, "gray")

    folium.Marker(
        location=[st.session_state.lat, st.session_state.lon],
        popup=str(f"Risk: {risk_cat}\nLoc: {st.session_state.location_name}"),
        tooltip=str("Click to view coordinates"),
        icon=folium.Icon(color=marker_color, icon="fire")
    ).add_to(m)

    # Render map and capture interaction
    map_data = st_folium(m, use_container_width=True, height=600)

    # Handle Map Clicks
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        
        if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
            st.session_state.lat = clicked_lat
            st.session_state.lon = clicked_lon
            st.session_state.prediction = None 
            
            try:
                location = geolocator.reverse((clicked_lat, clicked_lon), exactly_one=True)
                if location and location.address:
                    address_parts = location.address.split(",")
                    st.session_state.location_name = address_parts[0].strip()
                else:
                    st.session_state.location_name = "Custom Map Location"
            except:
                st.session_state.location_name = "Custom Map Location"
            
            st.rerun() 

# --- 4. Right Panel: Risk Analytics ---
with col_panel:
    st.subheader("Risk Analytics")

    if st.session_state.prediction:
        pred = st.session_state.prediction
        score = pred.get("risk_score", 0.0)
        cat = pred.get("risk_category", "Unknown")

        color_hex = {"Low": "#00C851", "Medium": "#FFBB33", "High": "#ff4444"}.get(cat, "#ffffff")

        st.markdown(f"""
            <div style="background-color: #262730; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #444; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                <p style="margin: 0; font-size: 1.1rem; color: #cccccc; text-transform: uppercase; letter-spacing: 1px;">Calculated Risk Score</p>
                <h1 style="margin: 15px 0; font-size: 4rem; color: {color_hex}; line-height: 1;">{score:.2f}</h1>
                <h3 style="margin: 0; color: {color_hex}; font-weight: 600; letter-spacing: 2px;">{cat.upper()} RISK</h3>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Environmental Features")
        
        # Pull the features dynamically from the session state
        curr_feat = st.session_state.current_features
        
        fc1, fc2 = st.columns(2)
        fc1.metric("Temperature", f"{curr_feat['temperature']} °C")
        fc2.metric("Humidity", f"{curr_feat['humidity']} %")
        fc1.metric("Wind Speed", f"{curr_feat['wind_speed']} km/h")
        fc2.metric("NDVI", f"{curr_feat['NDVI']}")
        st.metric("Terrain Slope", f"{curr_feat['slope']} °")

    else:
        st.info("Awaiting execution. Select a location and click 'Generate Risk Map' to view analytics.")
