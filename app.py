import folium
import requests
import streamlit as st
from streamlit_folium import st_folium

PREDICT_URL = "http://127.0.0.1:8000/predict"

st.set_page_config(
    page_title="Wildfire Risk Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

DARK_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

    html, body, [class*="css"]  {
        font-family: 'DM Sans', system-ui, sans-serif;
    }

    .stApp {
        background: linear-gradient(165deg, #0c0f14 0%, #12161f 45%, #0e1118 100%);
        color: #e8eaed;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #141821 0%, #0f1319 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.12);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .dashboard-header {
        margin-bottom: 0.35rem;
        letter-spacing: -0.02em;
        font-weight: 700;
        font-size: clamp(1.75rem, 3vw, 2.35rem);
        background: linear-gradient(120deg, #f8fafc 0%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .dashboard-subtitle {
        color: #8b9cb0;
        font-size: 1.05rem;
        font-weight: 500;
        margin-bottom: 2rem;
        letter-spacing: 0.01em;
    }

    .panel-title {
        color: #cbd5e1;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.75rem;
    }

    div[data-testid="column"] > div {
        padding-top: 0.25rem;
    }

    .stSlider label, [data-testid="stWidgetLabel"] {
        color: #cbd5e1 !important;
    }

    hr {
        border-color: rgba(148, 163, 184, 0.15) !important;
        margin: 1.25rem 0;
    }
</style>
"""

st.markdown(DARK_CSS, unsafe_allow_html=True)

if "risk_score" not in st.session_state:
    st.session_state.risk_score = None
if "risk_category" not in st.session_state:
    st.session_state.risk_category = None
if "predict_error" not in st.session_state:
    st.session_state.predict_error = None

DEFAULT_MAP_CENTER = [20.0, 78.0]
DEFAULT_ZOOM = 5

with st.sidebar:
    st.markdown('<p class="panel-title" style="margin-bottom:0.5rem;">Inputs</p>', unsafe_allow_html=True)
    st.caption("Environmental features for risk estimation")
    st.divider()

    temperature = st.slider("Temperature (°C)", -10.0, 55.0, 28.0, 0.5)
    ndvi = st.slider("NDVI", -1.0, 1.0, 0.35, 0.01)
    humidity = st.slider("Humidity (%)", 0.0, 100.0, 45.0, 1.0)
    wind_speed = st.slider("Wind speed (km/h)", 0.0, 120.0, 15.0, 1.0)
    slope = st.slider("Slope (°)", 0.0, 60.0, 8.0, 0.5)

    st.divider()
    generate_risk_map = st.button(
        "Generate Risk Map", type="primary", use_container_width=True
    )

if generate_risk_map:
    st.session_state.predict_error = None
    payload = {
        "temperature": temperature,
        "NDVI": ndvi,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "slope": slope,
    }
    try:
        response = requests.post(PREDICT_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        st.session_state.risk_score = float(data["risk_score"])
        st.session_state.risk_category = str(data["risk_category"])
    except requests.exceptions.RequestException as exc:
        st.session_state.predict_error = str(exc)
    except (KeyError, TypeError, ValueError) as exc:
        st.session_state.predict_error = f"Invalid response: {exc}"

st.markdown(
    '<h1 class="dashboard-header">Wildfire Risk Prediction Dashboard</h1>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="dashboard-subtitle">ML-powered early warning system</p>',
    unsafe_allow_html=True,
)

col_map, col_analytics = st.columns([1.65, 1.0], gap="large")

with col_map:
    st.markdown('<p class="panel-title">Map</p>', unsafe_allow_html=True)
    with st.container(border=True):
        m = folium.Map(
            location=DEFAULT_MAP_CENTER,
            zoom_start=DEFAULT_ZOOM,
            tiles="CartoDB dark_matter",
        )
        # Plain strings only — no callables, lambdas, or HTML callbacks (st_folium serialization)
        popup_label = "Study region"
        tooltip_label = "Study region"
        folium.Marker(
            location=DEFAULT_MAP_CENTER,
            popup=popup_label,
            tooltip=tooltip_label,
        ).add_to(m)
        st_folium(m, height=420, use_container_width=True)

with col_analytics:
    st.markdown('<p class="panel-title">Analytics</p>', unsafe_allow_html=True)

    with st.container(border=True):
        st.caption("Risk summary")
        c1, c2 = st.columns(2)
        rs = st.session_state.risk_score
        rc = st.session_state.risk_category
        with c1:
            st.metric(
                "Risk score",
                f"{rs:.4f}" if rs is not None else "—",
                help="From FastAPI /predict",
            )
        with c2:
            st.metric("Category", rc if rc is not None else "—")

    st.markdown("<br/>", unsafe_allow_html=True)

    with st.container(border=True):
        st.caption("Feature snapshot")
        st.json(
            {
                "temperature": temperature,
                "NDVI": ndvi,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "slope": slope,
            }
        )

    if st.session_state.predict_error:
        st.error(st.session_state.predict_error)
