import streamlit as st
import requests
import pandas as pd
import difflib

# Use Streamlit secrets for keys
LINZ_API_KEY = st.secrets["LINZ_API_KEY"]
GOOGLE_PLACES_KEY = st.secrets["GOOGLE_PLACES_KEY"]

# Load real data CSVs
pop_df = pd.read_csv('data/2023_Census_population_change_by_SA2_5545354433051253430.csv')
income_df = pd.read_csv('data/2023_Census_totals_by_topic_for_households_by_SA2_-132143055565075773.csv')

# Normalize main suburb name (column 4 is ASCII name)
pop_df['main_suburb'] = pop_df.iloc[:,3].astype(str).str.strip()
income_df['main_suburb'] = income_df.iloc[:,3].astype(str).str.strip()

# Session state
if "map_data" not in st.session_state:
    st.session_state.map_data = pd.DataFrame()
if "insights" not in st.session_state:
    st.session_state.insights = None
if "show_boundaries" not in st.session_state:
    st.session_state.show_boundaries = False

st.set_page_config(page_title="NZ Property Insights AI", layout="wide")
st.title("🏠 NZ Property Insights AI")
st.markdown("**Free tool** – Aerial + elevation + flood/coastal risk + suburb demographics (2023 Census)")

address = st.text_input("Enter NZ address or place:", placeholder="e.g. 23 queen street, petone or upper hutt college")

if st.button("🔍 Analyse Property", type="primary"):
    st.session_state.map_data = pd.DataFrame()
    st.session_state.insights = None

    with st.spinner("Searching location with Google Places..."):
        places_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": address,
            "inputtype": "textquery",
            "fields": "formatted_address,geometry",
            "key": GOOGLE_PLACES_KEY,
            "locationbias": "country:nz"
        }

        response = requests.get(places_url, params=params)
        data = response.json()

        if data["status"] != "OK" or not data["candidates"]:
            st.error("Location not found – try more specific")
            st.stop()

        candidate = data["candidates"][0]
        full_address = candidate["formatted_address"]
        short_address = full_address.split(',')[0]
        lat = candidate["geometry"]["location"]["lat"]
        lon = candidate["geometry"]["location"]["lng"]

        # Extract main suburb from formatted address (second part)
        address_parts = full_address.split(',')
        main_suburb = "Unknown"
        if len(address_parts) > 1:
            main_suburb = address_parts[1].strip().title()

        # Suburb display from formatted address
        suburb = main_suburb

        # Demographics – group all SA2s containing main_suburb
        income = "N/A"
        pop_2023 = "N/A"
        growth = "N/A"

        if main_suburb != "Unknown":
            # Find all SA2s containing the main suburb
            pop_matches = pop_df[pop_df['main_suburb'].str.contains(main_suburb, case=False, na=False)]
            income_matches = income_df[income_df['main_suburb'].str.contains(main_suburb, case=False, na=False)]

            if not pop_matches.empty:
                pop_cols = [col for col in pop_matches.columns if '2023' in col and 'population' in col.lower()]
                if pop_cols:
                    pop_total = pop_matches[pop_cols[0]].sum()
                    pop_2023 = int(pop_total) if pd.notna(pop_total) else "N/A"

                growth_cols = [col for col in pop_matches.columns if 'change' in col.lower() or 'growth' in col.lower()]
                if growth_cols:
                    growth_avg = pop_matches[growth_cols[0]].mean()
                    growth = f"{growth_avg:+.1f}" if pd.notna(growth_avg) else "N/A"

            if not income_matches.empty:
                income_cols = [col for col in income_matches.columns if 'median' in col.lower() and 'income' in col.lower()]
                if income_cols:
                    income_avg = income_matches[income_cols[0]].mean()
                    income = int(income_avg) if pd.notna(income_avg) else "N/A"

        # Elevation – safe handling
        elev_url = f"https://api.opentopodata.org/v1/nzdem8m?locations={lat},{lon}"
        elev_response = requests.get(elev_url)
        elev_data = elev_response.json()
        elev_value = elev_data["results"][0]["elevation"] if elev_data["status"] == "OK" and "elevation" in elev_data["results"][0] else None
        elevation = round(elev_value, 1) if elev_value is not None else "N/A"

        # Flood/Coastal Risk
        if isinstance(elevation, float):
            if elevation > 30:
                risk = "Low"
                risk_color = "green"
                risk_desc = "Well elevated – minimal flood/coastal risk"
            elif elevation > 10:
                risk = "Moderate"
                risk_color = "orange"
                risk_desc = "Some elevation – check local flood maps"
            else:
                risk = "High"
                risk_color = "red"
                risk_desc = "Low-lying – higher potential flood/coastal exposure"
        else:
            risk = "Unknown"
            risk_color = "gray"
            risk_desc = "Elevation data unavailable"

        # Resilience Score (0-100) – higher = lower flood risk + higher resilience
        resilience_score = 0
        if isinstance(elevation, float):
            # Elevation dominant – max 60 points
            if elevation > 50:
                resilience_score += 60
            elif elevation > 30:
                resilience_score += 50
            elif elevation > 10:
                resilience_score += 30
            elif elevation > 5:
                resilience_score += 15
            else:
                resilience_score += 0
        if growth != "N/A":
            growth_float = float(growth)
            # Growth bonus – max 20 points
            resilience_score += min(max(growth_float, 0) * 2, 20)
        if income != "N/A":
            # Income bonus – max 20 points
            resilience_score += min((income / 200000) * 20, 20)
        resilience_score = min(max(int(resilience_score), 0), 100)

        # Climate Resilience Rating (1-5 stars)
        if resilience_score >= 80:
            resilience = "★★★★★ Excellent"
        elif resilience_score >= 60:
            resilience = "★★★★ Very Good"
        elif resilience_score >= 40:
            resilience = "★★★ Good"
        elif resilience_score >= 20:
            resilience = "★★ Fair"
        else:
            resilience = "★ Poor"

        # Save
        st.session_state.insights = {
            "short_address": short_address,
            "suburb": suburb,
            "main_suburb": main_suburb,
            "elevation": elevation,
            "risk": risk,
            "risk_color": risk_color,
            "risk_desc": risk_desc,
            "income": income,
            "pop": pop_2023,
            "growth": growth,
            "resilience_score": resilience_score,
            "resilience": resilience,
            "lat": lat,
            "lon": lon
        }

        # Map data
        st.session_state.map_data = pd.DataFrame({
            "lat": [lat],
            "lon": [lon]
        })

# Display
if not st.session_state.map_data.empty and st.session_state.insights:
    i = st.session_state.insights

    st.success(f"**Found:** {i['short_address']} ({i['suburb']})")

    # Resilience Score with explanation
    st.markdown(f"### Resilience Score: **{i['resilience_score']}/100**")
    st.progress(i['resilience_score'] / 100)
    with st.expander("How is Resilience Score calculated?"):
        st.write("""
        Higher score = lower flood risk + higher suburb resilience.
        - Elevation: up to 60 points (higher elevation = safer from flood)
        - Population growth: up to 20 points (positive growth = bonus)
        - Median income: up to 20 points (affluent areas = bonus resilience)
        """)

    # Climate Resilience Rating with explanation
    st.markdown(f"### Climate Resilience Rating: {i['resilience']}")
    with st.expander("How is Climate Resilience calculated?"):
        st.write("""
        1-5 stars based on Resilience Score:
        - ★★★★★ Excellent (80+): Very resilient to climate risks
        - ★★★★ Very Good (60-79)
        - ★★★ Good (40-59)
        - ★★ Fair (20-39)
        - ★ Poor (0-19)
        """)

    cols = st.columns(3)
    with cols[0]:
        st.metric("Elevation (m)", i["elevation"])
    with cols[1]:
        st.markdown(f"**Flood/Coastal Risk**: <span style='color:{i['risk_color']}'>{i['risk']}</span>", unsafe_allow_html=True)
    with cols[2]:
        income_display = f"${i['income']:,}" if i['income'] != "N/A" else "N/A"
        st.metric("Median Income", income_display)

    pop_display = f"{i['pop']:,} ({i['growth']}% growth)" if i['pop'] != "N/A" else "N/A"
    st.metric("Population (2023)", pop_display)

    st.info(f"**Insight**: {i['risk_desc']} in {i['suburb']} (stats for main {i['main_suburb']})")

    st.markdown("### 🗺️ Map & Aerial View")
    st.map(st.session_state.map_data, zoom=18)

    # Property boundaries checkbox
    st.session_state.show_boundaries = st.checkbox("Show property boundaries", value=st.session_state.show_boundaries)

    if st.session_state.show_boundaries:
        boundaries_url = f"https://tiles.linz.govt.nz/services;key={LINZ_API_KEY}/tiles/v4/layer=50767/EPSG:3857/{{z}}/{{x}}/{{y}}.png"
        boundaries_html = f"""
        <div id="boundaries-map" style="width:100%; height:600px;"></div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script>
            var boundaries_map = L.map('boundaries-map').setView([{i['lat']}, {i['lon']}], 18);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap'
            }}).addTo(boundaries_map);
            L.tileLayer('{boundaries_url}', {{
                attribution: '© LINZ',
                opacity: 0.6
            }}).addTo(boundaries_map);
            L.marker([{i['lat']}, {i['lon']}]).addTo(boundaries_map)
                .bindPopup('{i['short_address']}')
                .openPopup();
        </script>
        """
        st.components.v1.html(boundaries_html, height=600)

    st.markdown("### 🤖 AI Summary")
    st.write(f"Property in {i['short_address']} ({i['suburb']}) at {i['elevation']}m – {i['risk']} flood/coastal risk.")
    st.write(f"**Resilience Score**: {i['resilience_score']}/100 | **Climate Resilience**: {i['resilience']}")
    if i['income'] != "N/A" and i['pop'] != "N/A":
        st.write(f"Main suburb {i['main_suburb']}: {i['pop']:,} residents ({i['growth']}% growth), median income ${i['income']:,}.")
        st.write("Strong for risk-aware investment in growing areas.")

    st.warning("Disclaimer: Public data – check official LIM/survey for accuracy.")

else:
    st.info("Enter any NZ address or place and click Analyse – results stay!")

st.caption("Free open data: LINZ + Open Topo | v9.5 – Built in NZ 🇳🇿")
