import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

# Page Configuration
st.set_page_config(
    page_title="Wildfire Risk Dashboard", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if 'prediction' not in st.session_state:
    st.session_state.prediction = None
if 'current_loc' not in st.session_state:
    st.session_state.current_loc = (34.0522, -118.2437)

# Default Model Features
default_features = {
    "temperature": 38.4,
    "NDVI": 0.24,
    "humidity": 14.0,
    "wind_speed": 28.0,
    "slope": 23.0
}

# 1. Sidebar Layout
with st.sidebar:
    st.title("🔥 Wildfire Prediction")
    st.markdown("---")
    
    aoi = st.selectbox("Area of Interest", ["Custom Location", "California", "Australia", "Mediterranean"])
    mode = st.radio("Selection Mode", ["Point", "Bounding Box"])
    
    lat = st.number_input("Latitude", value=34.0522, format="%.4f")
    lon = st.number_input("Longitude", value=-118.2437, format="%.4f")
    
    forecast = st.selectbox("Forecast Window", ["Next 24 Hours", "Next 48 Hours", "Next 7 Days"])
    
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("Generate Risk Map", type="primary", use_container_width=True)

# 2. Backend Integration & Error Handling
if generate_btn:
    with st.spinner("Analyzing satellite data & computing risk..."):
        try:
            response = requests.post(
                "http://127.0.0.1:8000/predict", 
                json=default_features, 
                timeout=10
            )
            if response.status_code == 200:
                st.session_state.prediction = response.json()
                st.session_state.current_loc = (lat, lon)
            else:
                st.sidebar.error(f"Backend Error: Received status code {response.status_code}")
        except requests.exceptions.RequestException:
            st.sidebar.error("Failed to connect to the backend. Please ensure the FastAPI server is running.")

# Layout: Main Center & Right Panel
col_map, col_panel = st.columns([2.5, 1], gap="large")

# 3. Main Center: Map View
with col_map:
    st.subheader("Geospatial Risk View")
    current_lat, current_lon = st.session_state.current_loc
    
    # Base Map
    m = folium.Map(
        location=[current_lat, current_lon], 
        zoom_start=10, 
        tiles="CartoDB dark_matter"
    )

    # 4 & 5. Map Marker logic (Strict string passing for JSON serialization)
    if st.session_state.prediction:
        risk_cat = st.session_state.prediction.get("risk_category", "Low")
        color_mapping = {"Low": "green", "Medium": "orange", "High": "red"}
        marker_color = color_mapping.get(risk_cat, "gray")

        folium.Marker(
            location=[current_lat, current_lon],
            popup=str(f"Risk Category: {risk_cat}"),
            tooltip=str("Selected Location"),
            icon=folium.Icon(color=marker_color, icon="fire")
        ).add_to(m)

    st_folium(m, use_container_width=True, height=600, returned_objects=[])

# 6. Right Panel: Risk Analytics & Features
with col_panel:
    st.subheader("Risk Analytics")

    if st.session_state.prediction:
        pred = st.session_state.prediction
        score = pred.get("risk_score", 0.0)
        cat = pred.get("risk_category", "Unknown")

        # Color hex codes for dark theme modern UI
        color_hex = {"Low": "#00C851", "Medium": "#FFBB33", "High": "#ff4444"}.get(cat, "#ffffff")

        # Risk Card
        st.markdown(f"""
            <div style="background-color: #262730; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #444; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                <p style="margin: 0; font-size: 1.1rem; color: #cccccc; text-transform: uppercase; letter-spacing: 1px;">Calculated Risk Score</p>
                <h1 style="margin: 15px 0; font-size: 4rem; color: {color_hex}; line-height: 1;">{score:.2f}</h1>
                <h3 style="margin: 0; color: {color_hex}; font-weight: 600; letter-spacing: 2px;">{cat.upper()} RISK</h3>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Environmental Features")
        
        # Displaying the default/simulated features gracefully
        fc1, fc2 = st.columns(2)
        fc1.metric("Temperature", f"{default_features['temperature']} °C")
        fc2.metric("Humidity", f"{default_features['humidity']} %")
        fc1.metric("Wind Speed", f"{default_features['wind_speed']} km/h")
        fc2.metric("NDVI", f"{default_features['NDVI']}")
        st.metric("Terrain Slope", f"{default_features['slope']} °")

    else:
        st.info("Awaiting execution. Configure your location parameters in the sidebar and click 'Generate Risk Map' to view analytics.")
